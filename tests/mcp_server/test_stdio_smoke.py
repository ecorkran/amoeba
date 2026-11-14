"""``amoeba-mcp`` over real stdio, driven by the SDK's client (slice 226, task 5.4).

The installed ``amoeba-mcp`` script starts as a child with a throwaway
``AMOEBA_HOME`` and fake ``cf`` and ``sq`` on ``PATH``. Leaving the client context
closes its stdin, which ends the server; the context returning within the timeout is
the proof that no child is left running.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anyio
import mcp_types as types
import pytest
from cf_fixtures import DEFAULT_WORKTREE, write_fake_cf
from fake_sq import write_fake_sq
from live_environment import process_environment
from mcp import ClientSession, StdioServerParameters, stdio_client
from user_configs import example_config_text

from amoeba.operations.names import OperationName

SERVER = Path(sys.executable).with_name("amoeba-mcp")
SYSTEM_PATH = "/usr/bin:/bin"
TIMEOUT_SECONDS = 60


def _parameters(tmp_path: Path) -> StdioServerParameters:
    bin_dir = tmp_path / "bin"
    write_fake_sq(bin_dir, waits={}, run_exit_code=0, run_stderr="")
    write_fake_cf(bin_dir, DEFAULT_WORKTREE)
    home = tmp_path / "home"
    (home / ".config" / "squadron" / "runs").mkdir(parents=True)
    amoeba_home = Path(os.environ["AMOEBA_HOME"])
    (amoeba_home / "config.yaml").write_text(example_config_text(), encoding="utf-8")
    return StdioServerParameters(
        command=str(SERVER),
        args=[],
        env=process_environment(
            os.environ,
            PATH=f"{bin_dir}{os.pathsep}{SYSTEM_PATH}",
            HOME=str(home),
            AMOEBA_HOME=str(amoeba_home),
        ),
        cwd=tmp_path,
    )


async def _list_and_call(
    parameters: StdioServerParameters,
) -> tuple[list[types.Tool], types.CallToolResult]:
    with anyio.fail_after(TIMEOUT_SECONDS):
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                decided = await session.call_tool("decisions", {})
    return listed.tools, decided


def test_the_client_lists_every_tool_and_calls_decisions(tmp_path: Path) -> None:
    parameters = _parameters(tmp_path)

    tools, decided = anyio.run(_list_and_call, parameters)

    assert {tool.name for tool in tools} == {name.value for name in OperationName}
    assert len(tools) == len(OperationName)
    assert {"add", "rm", "list"} <= {tool.name for tool in tools}
    assert "set_up" not in {tool.name for tool in tools}
    for tool in tools:
        assert tool.input_schema["type"] == "object", tool.name
    assert decided.is_error is False
    assert decided.structured_content is not None
    assert decided.structured_content["outcome"] == "listed"
    (block,) = decided.content
    assert isinstance(block, types.TextContent)
    assert json.loads(block.text) == decided.structured_content


def test_the_server_refuses_to_start_without_a_config(tmp_path: Path) -> None:
    parameters = _parameters(tmp_path)
    (Path(os.environ["AMOEBA_HOME"]) / "config.yaml").unlink()

    stderr_log = tmp_path / "server-stderr.log"

    async def start() -> None:
        with anyio.fail_after(TIMEOUT_SECONDS):
            with stderr_log.open("w", encoding="utf-8") as errlog:
                async with stdio_client(parameters, errlog=errlog) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()

    # The server exits at start-up, so the handshake ends in a closed connection
    # (the SDK raises it inside nested task-group groups).
    with pytest.raises(ExceptionGroup):
        anyio.run(start)

    reported = stderr_log.read_text(encoding="utf-8")
    assert "error: ConfigError: no config at" in reported, reported
