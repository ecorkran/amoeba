"""Slice 104 end to end, through the real CLI and demo script as subprocesses.

From an **empty** supervisor directory: start → create the project → stop →
seed a node → start → submit two review rounds and a provider failure →
resubmit round 1 under the same id → kill -9 → start. Read-only inspection
then shows three verdicts, round 2's changes, the failure refused as not comparable,
and nothing applied twice.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from cli_harness import (
    await_condition,
    await_stopped,
    cli_environment,
    run_cli,
    start_running,
    stop_running,
    submit_cli,
)

from amoeba.cli.main import ExitCode
from amoeba.inbox import pending
from amoeba.store import Store, SubmissionOutcome

PROJECT = "demo"
SCRIPTS = Path(__file__).parent.parent.parent / "scripts"
DEMO_SCRIPT = SCRIPTS / "demo_evidence.py"
PAYLOADS = SCRIPTS / "demo_evidence"


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """An empty supervisor directory. Never the real one."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    """An empty Squadron runs directory. Never the real one."""
    directory = tmp_path / "runs"
    directory.mkdir()
    return directory


def _store(supervisor_dir: Path) -> Path:
    return supervisor_dir / f"{PROJECT}.sqlite3"


def _applied(supervisor_dir: Path, *submission_ids: str) -> bool:
    if not _store(supervisor_dir).is_file():
        return False
    with Store.open_read_only(_store(supervisor_dir)) as store:
        records = [store.submission(sid) for sid in submission_ids]
    return all(
        r is not None and r.outcome is SubmissionOutcome.APPLIED for r in records
    )


def _seed_node(supervisor_dir: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(DEMO_SCRIPT)],
        capture_output=True,
        text=True,
        env=cli_environment(supervisor_dir),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _submit_verdict(supervisor_dir: Path, node: str, *flags: str) -> str:
    return submit_cli(
        supervisor_dir,
        PROJECT,
        "verdict",
        "--by",
        "pm",
        "--node-id",
        node,
        "--review-type",
        "tasks",
        "--model",
        "demo-model",
        "--upstream",
        "squadron",
        "--upstream-version",
        "0.14.0",
        "--source",
        "artifact_frontmatter",
        "--fallback-used",
        "null",
        *flags,
    )


def _round(supervisor_dir: Path, node: str, verdict_id: str, payload: str) -> str:
    return _submit_verdict(
        supervisor_dir,
        node,
        "--id",
        verdict_id,
        "--verdict",
        "CONCERNS",
        "--derivation",
        "stated",
        "--provider-failure",
        "false",
        "--findings-parsed",
        "true",
        "--findings",
        (PAYLOADS / payload).read_text(),
    )


def _inspect(supervisor_dir: Path, *arguments: str) -> list[dict[str, object]]:
    result = run_cli(
        ["inspect", *arguments, "--project", PROJECT, "--json"], supervisor_dir
    )
    assert result.returncode == ExitCode.OK, result.stderr
    rows: list[dict[str, object]] = json.loads(result.stdout)
    return rows


def _snapshot(supervisor_dir: Path) -> str:
    return json.dumps(
        [
            _inspect(supervisor_dir, "verdicts"),
            _inspect(supervisor_dir, "findings"),
            _inspect(supervisor_dir, "submissions"),
        ]
    )


def test_the_slice_end_to_end_through_the_real_cli(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    process = start_running(supervisor_dir, runs_dir)
    created = submit_cli(supervisor_dir, PROJECT, "create-project", "--by", "pm")
    await_condition(lambda: _applied(supervisor_dir, created), "project creation")
    stop_running(supervisor_dir, process)

    node = _seed_node(supervisor_dir)
    process = start_running(supervisor_dir, runs_dir)

    _round(supervisor_dir, node, "r1", "round1.json")
    _round(supervisor_dir, node, "r2", "round2.json")
    _submit_verdict(
        supervisor_dir,
        node,
        "--id",
        "r3",
        "--verdict",
        "UNKNOWN",
        "--derivation",
        "not_reported",
        "--provider-failure",
        "true",
        "--findings-parsed",
        "null",
        "--findings",
        "[]",
    )
    await_condition(lambda: _applied(supervisor_dir, "r1", "r2", "r3"), "3 reviews")

    # A retry of round 1 under the same id is drained and changes nothing.
    _round(supervisor_dir, node, "r1", "round1.json")
    await_condition(lambda: pending(supervisor_dir) == [], "the retry to drain")
    before = _snapshot(supervisor_dir)

    process.kill_and_wait()
    process.cleanup()
    await_stopped(supervisor_dir)
    process = start_running(supervisor_dir, runs_dir)
    try:
        assert _snapshot(supervisor_dir) == before
        assert pending(supervisor_dir) == []
    finally:
        stop_running(supervisor_dir, process)

    verdicts = _inspect(supervisor_dir, "verdicts")
    assert [(v["id"], v["standing"]) for v in verdicts] == [
        ("r1", "stated"),
        ("r2", "stated"),
        ("r3", "provider_failure"),
    ]
    changes = _inspect(supervisor_dir, "changes", "--verdict", "r2")
    assert [row["change"] for row in changes] == ["new", "recurring", "gone"]
    assert {row["previous_verdict_id"] for row in changes} == {"r1"}

    failure = run_cli(
        ["inspect", "changes", "--project", PROJECT, "--verdict", "r3"],
        supervisor_dir,
    )
    assert failure.returncode == ExitCode.NOT_COMPARABLE, failure.stderr

    submissions = _inspect(supervisor_dir, "submissions")
    assert [row["id"] for row in submissions] == [created, "r1", "r2", "r3"]
