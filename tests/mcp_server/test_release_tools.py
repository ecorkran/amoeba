"""``report_release`` and ``changes`` give the same result through both doors
(slice 227, 4.3): the CLI as a real subprocess, the MCP tool through ``call_tool``,
a fake ``cf`` first on ``PATH`` for both and the real operations behind them.

226's parity tests already cover the rows and the ``directory`` rule.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anyio
import mcp_types as types
import pytest
from cf_fixtures import DEFAULT_WORKTREE, write_fake_cf_with_projects
from cli.cli_support import PROJECT_ID, result_of, run_amoeba, write_config
from store.seed import insert_member, insert_pair

from amoeba.cli.exit_codes import EXIT_OK, EXIT_REJECTED
from amoeba.config.home import store_path
from amoeba.mcp import server
from amoeba.store import releases
from amoeba.store.programs import get_member
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import ConsumedMode

FULL_HASH = "cd34" * 10
SEEDED_HASH = "ef56" * 10
PROVIDER_ID = "provider-not-named-by-cf"
SINCE = "2026-11-09T12:00:00+00:00"
SEEDED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
#: Wall-clock fields; everything else in a result is deterministic.
CLOCK_FIELDS = ("reported_at", "versioned_at")


@pytest.fixture(autouse=True)
def _fake_cf_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The MCP door runs ``cf`` in this process, so ``PATH`` must find the fake."""
    bin_dir = tmp_path / "bin"
    write_fake_cf_with_projects(bin_dir, DEFAULT_WORKTREE)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def _use_home(monkeypatch: pytest.MonkeyPatch, home: Path, tmp_path: Path) -> None:
    """A fresh Amoeba home with this repo registered."""
    monkeypatch.setenv("AMOEBA_HOME", str(home))
    write_config()
    assert run_amoeba(tmp_path, "add").returncode == EXIT_OK


def _through_mcp(
    name: str, arguments: Mapping[str, object]
) -> tuple[dict[str, Any], bool]:
    async def run() -> types.CallToolResult:
        return await server.call_tool(name, arguments)

    result = anyio.run(run)
    (block,) = result.content
    assert isinstance(block, types.TextContent)
    document: dict[str, Any] = json.loads(block.text)
    return document, bool(result.is_error)


def _drop_clock(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    return {key: value for key, value in pairs if key not in CLOCK_FIELDS}


def _without_clock(document: dict[str, Any]) -> dict[str, Any]:
    """``document`` with the wall-clock fields of every report removed."""
    stripped: dict[str, Any] = json.loads(
        json.dumps(document), object_pairs_hook=_drop_clock
    )
    return stripped


def _seed_provider(tmp_path: Path) -> None:
    """A provider this repo consumes, with one report; the names ``cf`` gives do not
    include it, so the result also carries the warning."""
    with Store.open(store_path()) as store, store.write() as transaction:
        program = _program_of(transaction)
        insert_member(
            transaction,
            project_id=PROVIDER_ID,
            program_id=program,
            rules_paths=(),
            authorize_allow=(),
            authorize_deny=(),
            registered_at=SEEDED_AT,
            updated_at=SEEDED_AT,
        )
        insert_pair(
            transaction,
            program_id=program,
            provider_id=PROVIDER_ID,
            consumer_id=PROJECT_ID,
            consumed=ConsumedMode.FROM_SOURCE,
            registered_at=SEEDED_AT,
            updated_at=SEEDED_AT,
        )
        releases.insert_release(
            transaction, PROVIDER_ID, SEEDED_HASH, None, "seeded", ("api",), SEEDED_AT
        )


def _program_of(transaction: Transaction) -> str:
    member = get_member(transaction, PROJECT_ID)
    assert member is not None
    return member.program_id


def test_report_release_gives_equal_results_through_both_doors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_home(monkeypatch, tmp_path / "home-cli", tmp_path)
    completed = run_amoeba(
        tmp_path,
        "report-release",
        "--commit",
        FULL_HASH,
        "--version",
        "tag-one",
        "--changed",
        "what changed",
        "--touched",
        "one",
        "--touched",
        "two",
        as_json=True,
    )
    assert completed.returncode == EXIT_OK, completed.stderr
    _use_home(monkeypatch, tmp_path / "home-mcp", tmp_path)

    document, is_error = _through_mcp(
        "report_release",
        {
            "directory": str(tmp_path),
            "commit": FULL_HASH,
            "version": "tag-one",
            "changed": "what changed",
            "touched": ["one", "two"],
        },
    )

    assert not is_error
    assert document["outcome"] == "recorded"
    assert _without_clock(document) == _without_clock(result_of(completed))


def test_changes_gives_equal_results_through_both_doors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_home(monkeypatch, tmp_path / "home", tmp_path)
    _seed_provider(tmp_path)
    completed = run_amoeba(tmp_path, "changes", "--since", SINCE, as_json=True)
    assert completed.returncode == EXIT_OK, completed.stderr

    document, is_error = _through_mcp(
        "changes", {"directory": str(tmp_path), "since": SINCE}
    )

    assert not is_error
    assert document == result_of(completed)
    (pair,) = document["pairs"]
    assert pair["provider"] == {"id": PROVIDER_ID, "name": None}
    assert [report["commit"] for report in pair["releases"]] == [SEEDED_HASH]
    assert [warning["code"] for warning in document["warnings"]] == [
        "not_in_context_forge"
    ]


@pytest.mark.parametrize(
    ("command", "arguments"),
    [
        (
            "report-release",
            ("--commit", FULL_HASH, "--changed", "text", "--touched", "item"),
        ),
        ("changes", ("--since", SINCE)),
    ],
)
def test_a_directory_in_no_program_is_not_a_member_through_both_doors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    arguments: tuple[str, ...],
) -> None:
    # Nothing is registered, so the project is in no program.
    monkeypatch.setenv("AMOEBA_HOME", str(tmp_path / "home"))
    write_config()
    completed = run_amoeba(tmp_path, command, *arguments, as_json=True)
    assert completed.returncode == EXIT_REJECTED

    tool_arguments: dict[str, object] = {"directory": str(tmp_path)}
    tool_arguments.update(
        {
            "commit": FULL_HASH,
            "changed": "text",
            "touched": ["item"],
        }
        if command == "report-release"
        else {"since": SINCE}
    )
    document, is_error = _through_mcp(command.replace("-", "_"), tool_arguments)

    assert not is_error
    assert document == result_of(completed)
    assert document["problems"][0]["code"] == "not_a_member"
    with Store.open(store_path()) as store, store.read() as transaction:
        count = transaction.execute("SELECT COUNT(*) FROM releases").fetchone()
    assert count is not None
    assert count[0] == 0
