"""``send``, ``inbox``, ``reply`` and ``cancel`` give the same result through both doors
(slice 240): the CLI as a real subprocess, the MCP tool through ``call_tool``, a fake
``cf`` first on ``PATH`` for both and the real operations behind them.

The rows, the ``directory`` rule and the notice are in ``test_tools.py``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import anyio
import mcp_types as types
import pytest
from cf_fixtures import DEFAULT_WORKTREE, write_fake_cf_with_projects
from cli.cli_support import PROJECT_NAME, result_of, run_amoeba, write_config

from amoeba.cli.exit_codes import EXIT_OK, EXIT_REJECTED
from amoeba.mcp import server
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from mcp_server.presence_rig import idle_presence

#: Wall-clock fields; everything else in a result is deterministic.
CLOCK_FIELDS = {"created_at", "accepted_at", "state_changed_at", "expires_at"}
HASH = "ab12" * 10
SEND_CLI = (
    "send",
    "--id",
    "ask-1",
    "--to",
    PROJECT_NAME,
    "--subject",
    "a subject",
    "--body",
    "a body",
)
SEND_TOOL: dict[str, object] = {
    "id": "ask-1",
    "to": PROJECT_NAME,
    "subject": "a subject",
    "body": "a body",
}


@pytest.fixture(autouse=True)
def _fake_cf_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The MCP door runs ``cf`` in this process, so ``PATH`` must find the fake."""
    bin_dir = tmp_path / "bin"
    write_fake_cf_with_projects(bin_dir, DEFAULT_WORKTREE)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def _use_home(
    monkeypatch: pytest.MonkeyPatch,
    home: Path,
    tmp_path: Path,
    before: Sequence[Sequence[str]],
) -> None:
    """A fresh Amoeba home with this repo registered and ``before`` run on the CLI."""
    monkeypatch.setenv("AMOEBA_HOME", str(home))
    write_config()
    assert run_amoeba(tmp_path, "add").returncode == EXIT_OK
    for arguments in before:
        assert run_amoeba(tmp_path, *arguments).returncode == EXIT_OK


def _through_mcp(
    name: str, arguments: Mapping[str, object]
) -> tuple[dict[str, Any], bool]:
    async def run() -> types.CallToolResult:
        return await server.call_tool(name, arguments, idle_presence())

    result = anyio.run(run)
    (block,) = result.content
    assert isinstance(block, types.TextContent)
    document: dict[str, Any] = json.loads(block.text)
    return document, bool(result.is_error)


def _drop_clock(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    return {key: value for key, value in pairs if key not in CLOCK_FIELDS}


def _without_clock(document: dict[str, Any]) -> dict[str, Any]:
    stripped: dict[str, Any] = json.loads(
        json.dumps(document), object_pairs_hook=_drop_clock
    )
    return stripped


def _compare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    before: Sequence[Sequence[str]],
    cli: Sequence[str],
    tool: str,
    arguments: Mapping[str, object],
    exit_code: int,
) -> dict[str, Any]:
    """Run ``cli`` in one fresh home and ``tool`` in another, each after ``before``,
    and return the (equal) result document."""
    _use_home(monkeypatch, tmp_path / "home-cli", tmp_path, before)
    completed = run_amoeba(tmp_path, *cli, as_json=True)
    assert completed.returncode == exit_code, completed.stderr
    _use_home(monkeypatch, tmp_path / "home-mcp", tmp_path, before)

    document, is_error = _through_mcp(tool, {"directory": str(tmp_path), **arguments})

    assert not is_error
    assert _without_clock(document) == _without_clock(result_of(completed))
    assert document["notice"] == QUOTED_DATA_NOTICE
    return document


def test_send_gives_equal_results_through_both_doors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _compare(
        tmp_path,
        monkeypatch,
        before=[],
        cli=SEND_CLI,
        tool="send",
        arguments=SEND_TOOL,
        exit_code=EXIT_OK,
    )

    assert document["outcome"] == "sent"
    assert document["request"]["id"] == "ask-1"


def test_a_rejected_send_gives_equal_results_through_both_doors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _compare(
        tmp_path,
        monkeypatch,
        before=[],
        cli=(*SEND_CLI, "--parent", "nowhere"),
        tool="send",
        arguments={**SEND_TOOL, "parent": "nowhere"},
        exit_code=EXIT_REJECTED,
    )

    assert document["rejection"] == "parent_unknown"


def test_inbox_gives_equal_results_through_both_doors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _compare(
        tmp_path,
        monkeypatch,
        before=[SEND_CLI],
        cli=("inbox", "--since", "0"),
        tool="inbox",
        arguments={"since": 0},
        exit_code=EXIT_OK,
    )

    assert [item["message_id"] for item in document["deliveries"]] == ["ask-1"]
    assert document["as_of_seq"] == 1


def test_reply_gives_equal_results_through_both_doors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _compare(
        tmp_path,
        monkeypatch,
        before=[SEND_CLI, ("reply", "ask-1", "accept")],
        cli=("reply", "ask-1", "done", "--text", "shipped", "--commit", HASH),
        tool="reply",
        arguments={"id": "ask-1", "action": "done", "text": "shipped", "commit": HASH},
        exit_code=EXIT_OK,
    )

    assert document["request"]["state"] == "done"


def test_a_rejected_reply_gives_equal_results_through_both_doors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _compare(
        tmp_path,
        monkeypatch,
        before=[],
        cli=("reply", "nothing", "accept"),
        tool="reply",
        arguments={"id": "nothing", "action": "accept"},
        exit_code=EXIT_REJECTED,
    )

    assert document["rejection"] == "unknown_request"


def test_cancel_gives_equal_results_through_both_doors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _compare(
        tmp_path,
        monkeypatch,
        before=[SEND_CLI],
        cli=("cancel", "ask-1", "--reason", "not needed"),
        tool="cancel",
        arguments={"id": "ask-1", "reason": "not needed"},
        exit_code=EXIT_OK,
    )

    assert document["request"]["state"] == "cancelled"


def test_a_message_tool_without_a_directory_is_an_error_naming_the_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_home(monkeypatch, tmp_path / "home", tmp_path, [])

    for name in ("send", "inbox", "reply", "cancel"):

        async def run(tool: str = name) -> types.CallToolResult:
            return await server.call_tool(tool, {}, idle_presence())

        result = anyio.run(run)
        (block,) = result.content
        assert isinstance(block, types.TextContent)
        assert result.is_error, name
        assert "directory is required" in block.text
