"""Slice 103 end to end, through the real CLI and demo script as subprocesses.

From an **empty** supervisor directory: start → submit create-project → stop →
seed a human-blocked node → read its escalation row read-only → submit a
resolution while stopped → start → the node is runnable → kill -9 → start →
state unchanged and nothing applied twice.

Seeding happens while the process is stopped, not while it runs: the demo
script opens the store read-write, so it takes the instance lock and refuses
while the process holds it. That is the single-writer model working.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from cli_harness import (
    BackgroundCli,
    await_running,
    await_stopped,
    cli_environment,
    run_cli,
    start_background,
)

from amoeba.cli.main import ExitCode
from amoeba.inbox import pending
from amoeba.store import Channel, NodeStatus, Store, SubmissionOutcome

PROJECT = "demo"
DEMO_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "demo_inbox.py"

#: A running process applies on its next tick; generous for a loaded machine.
APPLY_TIMEOUT_SECONDS = 20.0


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


def _start(supervisor_dir: Path, runs_dir: Path) -> BackgroundCli:
    process = start_background(
        supervisor_dir, ["--sq-runs-dir", str(runs_dir), "--idle-interval", "0.05"]
    )
    await_running(supervisor_dir)
    return process


def _stop(supervisor_dir: Path, process: BackgroundCli) -> None:
    assert run_cli(["stop"], supervisor_dir).returncode == ExitCode.OK
    assert process.wait() == ExitCode.OK
    process.cleanup()


def _await(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + APPLY_TIMEOUT_SECONDS
    while not condition():
        assert time.monotonic() < deadline, f"{what} did not happen"
        time.sleep(0.05)


def _submit(supervisor_dir: Path, *arguments: str) -> str:
    result = run_cli(["submit", *arguments, "--project", PROJECT], supervisor_dir)
    assert result.returncode == ExitCode.OK, result.stderr
    return result.stdout.strip()


def _outcome(supervisor_dir: Path, submission_id: str) -> SubmissionOutcome | None:
    with Store.open_read_only(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        record = store.submission(submission_id)
    return None if record is None else record.outcome


def _seed_blocked_node(supervisor_dir: Path) -> tuple[str, str]:
    """Run the real demo script; return (node id, blocked-state id)."""
    result = subprocess.run(
        [sys.executable, str(DEMO_SCRIPT)],
        capture_output=True,
        text=True,
        env=cli_environment(supervisor_dir),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    fields = dict(
        line.split(":", 1) for line in result.stdout.splitlines() if ":" in line
    )
    return fields["node id"].strip(), fields["blocked state id"].strip()


def _snapshot(supervisor_dir: Path) -> str:
    """Every record and every message, as JSON, for before/after comparison."""
    submissions = run_cli(
        ["inspect", "submissions", "--project", PROJECT, "--json"], supervisor_dir
    ).stdout
    messages = run_cli(
        ["inspect", "messages", "--project", PROJECT, "--json"], supervisor_dir
    ).stdout
    return json.dumps([json.loads(submissions), json.loads(messages)])


def test_the_slice_end_to_end_through_the_real_cli(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    # A running process creates the project.
    process = _start(supervisor_dir, runs_dir)
    created = _submit(supervisor_dir, "create-project", "--by", "pm")
    _await(
        lambda: (
            (supervisor_dir / f"{PROJECT}.sqlite3").is_file()
            and _outcome(supervisor_dir, created) is SubmissionOutcome.APPLIED
        ),
        "project creation",
    )
    listing = run_cli(["inspect", "projects", "--json"], supervisor_dir)
    assert [row["project_id"] for row in json.loads(listing.stdout)] == [PROJECT]
    _stop(supervisor_dir, process)

    # Seed a human-blocked node while stopped; its escalation is readable at once.
    node_id, blocked_state_id = _seed_blocked_node(supervisor_dir)
    with Store.open_read_only(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        [escalation] = store.messages(PROJECT, channel=Channel.ESCALATION)
    assert (escalation.node_id, escalation.blocked_state_id) == (
        node_id,
        blocked_state_id,
    )

    # Submit the resolution with the process down; start applies it.
    resolution = _submit(
        supervisor_dir,
        "resolution",
        "--by",
        "pm",
        "--blocked-state-id",
        blocked_state_id,
        "--detail",
        "proceed",
    )
    assert _outcome(supervisor_dir, resolution) is None
    process = _start(supervisor_dir, runs_dir)
    _await(
        lambda: _outcome(supervisor_dir, resolution) is SubmissionOutcome.APPLIED,
        "the resolution",
    )
    with Store.open_read_only(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        node = store.get_node(node_id)
    assert node is not None and node.status is NodeStatus.RUNNABLE
    before = _snapshot(supervisor_dir)

    # kill -9, then start: nothing changes and nothing applies twice.
    process.kill_and_wait()
    process.cleanup()
    await_stopped(supervisor_dir)
    process = _start(supervisor_dir, runs_dir)
    try:
        assert _snapshot(supervisor_dir) == before
        assert pending(supervisor_dir) == []
    finally:
        _stop(supervisor_dir, process)

    with Store.open_read_only(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        assert [record.id for record in store.submissions(PROJECT)] == [
            created,
            resolution,
        ]
        node = store.get_node(node_id)
    assert node is not None and node.status is NodeStatus.RUNNABLE
