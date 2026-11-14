"""The slice 226 verification walkthrough, steps 3 to 5, with real ``sq``, ``cf`` and
models (slice 226, task 6.2).

A throwaway member (its own Context Forge data directory and ``AMOEBA_HOME``) runs
real pipelines that pause on a question. ``amoeba-mcp`` is driven by the SDK's stdio
client from a directory in no program, one session per call (so the detached
``handle_pause`` child is shown to outlive the server that started it); the CLI is the
reference for what each tool must return. A do-nothing ``amoeba`` is first on ``PATH``,
so the pause hook (configured user-level) never handles a pause behind the test's
back. A wrong result fails the test; nothing is retried.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import anyio
import mcp_types as types
import yaml
from live_harness import POLL_INTERVAL_SECONDS
from live_settings import LiveSettings
from mcp import ClientSession, StdioServerParameters, stdio_client

from amoeba.config.home import calls_log_dir
from amoeba.operations.names import OperationName
from amoeba.upstream.squadron.launch import mint_run_id
from amoeba.upstream.squadron.run_outcome import (
    RunOutcome,
    RunOutcomeDocument,
    poll_run,
)
from live.pause.harness import (
    PauseWorld,
    inert_hook,
    result_of,
    run_amoeba,
    start_pause,
)

UNSETTLED_PIPELINE: Final = (
    Path(__file__).parent.parent / "pause" / "asks_unsettled_question.yaml"
)
MCP_SERVER: Final = Path(sys.executable).with_name("amoeba-mcp")
#: ``amoeba-mcp`` refuses a ``resume_wait_seconds`` whose ``answer`` bound reaches its
#: call deadline, so the world's config is lowered from the pause tier's value.
RESUME_WAIT_SECONDS: Final = 60
SESSION_TIMEOUT_SECONDS: Final = 600
DETACHED_RESULT_SECONDS: Final = 900
POLL_CALL_TIMEOUT_SECONDS: Final = 30.0
ANSWER_TEXT: Final = "Use teal."


def _lower_resume_wait(world: PauseWorld) -> None:
    config_file = world.amoeba_home / "config.yaml"
    config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    config["resume_wait_seconds"] = RESUME_WAIT_SECONDS
    config_file.write_text(yaml.safe_dump(config), encoding="utf-8")


def _server(world: PauseWorld, workdir: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=str(MCP_SERVER), args=[], env=world.environ, cwd=workdir
    )


def _list_tools(world: PauseWorld, workdir: Path) -> list[types.Tool]:
    async def run() -> list[types.Tool]:
        with anyio.fail_after(SESSION_TIMEOUT_SECONDS):
            async with stdio_client(_server(world, workdir)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return (await session.list_tools()).tools

    return anyio.run(run)


def _tool(
    world: PauseWorld, workdir: Path, name: str, arguments: dict[str, object]
) -> dict[str, Any]:
    """One tool call in its own session; the call must be a result, not an error."""

    async def run() -> types.CallToolResult:
        with anyio.fail_after(SESSION_TIMEOUT_SECONDS):
            async with stdio_client(_server(world, workdir)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(name, arguments)

    result = anyio.run(run)
    assert result.is_error is False, result.content
    assert result.structured_content is not None, result.content
    (block,) = result.content
    assert isinstance(block, types.TextContent)
    assert json.loads(block.text) == result.structured_content
    return dict(result.structured_content)


def _amoeba(
    world: PauseWorld, *arguments: str, cwd: Path | None = None, expect: int = 0
) -> dict[str, Any]:
    completed = run_amoeba(world, *arguments, cwd=cwd)
    assert completed.returncode == expect, (
        f"amoeba {' '.join(arguments)} exited {completed.returncode}\n"
        f"{completed.stdout}\n{completed.stderr}"
    )
    return dict(result_of(completed))


def _new_run(world: PauseWorld) -> str:
    """Start a run that pauses on a question no rule settles, without a hook."""
    run_id = mint_run_id(datetime.now(UTC))
    started = start_pause(world, run_id, opt_out=True, pipeline=UNSETTLED_PIPELINE)
    assert isinstance(started.poll, RunOutcomeDocument), started.sq_output
    poll = poll_run(run_id, timeout_seconds=POLL_CALL_TIMEOUT_SECONDS)
    assert isinstance(poll, RunOutcomeDocument), poll
    assert poll.outcome is RunOutcome.PAUSED, poll
    return run_id


def _member(status: dict[str, Any]) -> dict[str, Any]:
    (program,) = status["programs"]
    (member,) = program["members"]
    entry: dict[str, Any] = member
    return entry


def _run_entry(status: dict[str, Any], run_id: str) -> dict[str, Any]:
    (entry,) = [run for run in _member(status)["runs"] if run["run_id"] == run_id]
    found: dict[str, Any] = entry
    return found


def _log_result(path: Path) -> dict[str, Any]:
    """The JSON a detached ``handle_pause`` wrote to its stdout log, once it has."""
    deadline = time.monotonic() + DETACHED_RESULT_SECONDS
    while time.monotonic() < deadline:
        if path.exists() and path.read_text(encoding="utf-8").strip():
            document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return document
        time.sleep(POLL_INTERVAL_SECONDS)
    raise AssertionError(f"{path} stayed empty for {DETACHED_RESULT_SECONDS}s")


def _calls_logged_for(run_id: str) -> list[dict[str, Any]]:
    """The calls-log lines of ``run_id`` (the test's ``AMOEBA_HOME`` is the world's)."""
    return [
        entry
        for day in sorted(calls_log_dir().glob("*.jsonl"))
        for entry in map(json.loads, day.read_text(encoding="utf-8").splitlines())
        if entry["run_id"] == run_id
    ]


def test_the_mcp_walkthrough(
    pause_world: PauseWorld, live_settings: LiveSettings, tmp_path: Path
) -> None:
    del live_settings
    world = inert_hook(pause_world)
    _lower_resume_wait(world)
    workdir = tmp_path / "elsewhere"
    workdir.mkdir()

    # Step 3: every tool; list, status, decisions, mark_read and add agree with the CLI.
    tools = _list_tools(world, workdir)
    assert {tool.name for tool in tools} == {name.value for name in OperationName}
    assert len(tools) == len(OperationName)
    assert {"add", "rm", "list"} <= {tool.name for tool in tools}
    assert "set_up" not in {tool.name for tool in tools}
    first, second, third = (_new_run(world) for _ in range(3))
    status = _tool(world, workdir, "status", {"directory": str(workdir)})
    assert status == _amoeba(world, "status", cwd=workdir)
    assert status["outcome"] == "listed"
    listed_view = _tool(world, workdir, "list", {"directory": str(workdir)})
    assert listed_view == status == _amoeba(world, "list", cwd=workdir)
    members = _tool(
        world, workdir, "list", {"subject": "members", "directory": str(workdir)}
    )
    assert members == _amoeba(world, "list", "members", cwd=workdir)
    (member_row,) = members["members"]
    assert member_row["rules_from"] == "config_default", member_row
    repo_args: dict[str, object] = {"directory": str(world.repo)}
    again = _tool(world, workdir, "add", repo_args)
    assert again["outcome"] == "unchanged", again
    assert again == _amoeba(world, "add")
    stranger = _tool(world, workdir, "rm", {"members": ["no-such-member"], **repo_args})
    assert stranger["outcome"] == "rejected", stranger
    assert [p["code"] for p in stranger["problems"]] == ["not_a_member"]
    empty = _tool(world, workdir, "decisions", {})
    assert empty == _amoeba(world, "decisions")
    assert empty["records"] == []
    unchanged = _tool(world, workdir, "mark_read", {"through": 0})
    assert unchanged == _amoeba(world, "mark-read", "--through", "0")
    assert unchanged["outcome"] == "unchanged"

    # Step 4: handle_pause returns a receipt at once; the child's log gets the result.
    entry = _run_entry(status, first)
    assert entry["pause"] == "unhandled", entry
    receipt = _tool(
        world,
        workdir,
        "handle_pause",
        {"run_id": first, "directory": entry["next"]["directory"]},
    )
    assert receipt["operation"] == "handle_pause"
    assert isinstance(receipt["pid"], int)
    handled = _log_result(Path(receipt["stdout_log"]))
    assert handled["outcome"] == "waiting_on_pm", handled
    (logged,) = _calls_logged_for(first)
    assert logged["outcome"] == "waiting_on_pm", logged
    for run_id in (second, third):
        declined = _amoeba(world, "handle-pause", run_id)
        assert declined["outcome"] == "waiting_on_pm", declined

    # Step 5: answer through MCP and through the CLI; dismiss; retract.
    by_mcp = _tool(world, workdir, "answer", {"run_id": first, "text": ANSWER_TEXT})
    assert by_mcp["outcome"] == "recorded", by_mcp
    assert by_mcp["resume"] is not None
    by_cli = _amoeba(world, "answer", second, "--text", ANSWER_TEXT)
    assert by_cli["outcome"] == "recorded", by_cli
    listed = _tool(world, workdir, "decisions", {})
    assert listed == _amoeba(world, "decisions")
    doors = {record["run_id"]: record["via"] for record in listed["records"]}
    assert doors[first] == "mcp" and doors[second] == "cli", doors
    dismissed = _tool(
        world, workdir, "dismiss", {"run_id": third, "reason": "not needed"}
    )
    assert dismissed["outcome"] == "dismissed", dismissed
    retracted = _tool(
        world,
        workdir,
        "retract",
        {"answer_seq": by_mcp["answer_seq"], "reason": "the PM changed their mind"},
    )
    assert retracted["outcome"] == "retracted", retracted
    moved = _tool(world, workdir, "mark_read", {"through": listed["read_through"]})
    assert moved["outcome"] == "moved", moved
    assert _amoeba(world, "decisions")["records"] == []
