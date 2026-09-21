"""Tests for ``start``, ``stop``, and ``status``, driving the real CLI.

Every invocation is a real subprocess with ``AMOEBA_STORE_DIR`` pointed at a
directory under ``tmp_path``. Nothing here mocks locking or signals.

``tests/test_cli_safety.py`` separately proves, mechanically, that no test in
this tier can reach the real supervisor directory or the real Squadron runs
directory.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from cli_harness import (
    await_running,
    await_stopped,
    run_cli,
    start_background,
)

from amoeba.cli.main import ExitCode
from amoeba.store import BlockedKind, CommandKind, NodeKind, Store
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    read_schema_version,
)

PROJECT = "demo"


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """A throwaway supervisor directory. Never the real one."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    """An empty Squadron runs directory. Never the real one."""
    directory = tmp_path / "runs"
    directory.mkdir()
    return directory


def _start_arguments(runs_dir: Path) -> list[str]:
    """Flags every backgrounded start uses, keeping it off the real runs dir."""
    return ["--sq-runs-dir", str(runs_dir), "--idle-interval", "0.05"]


# --------------------------------------------------------------------------
# The full cycle
# --------------------------------------------------------------------------


def test_start_status_stop_status(supervisor_dir: Path, runs_dir: Path) -> None:
    """The headline claim: start, see it running, stop it, see it stopped."""
    process = start_background(supervisor_dir, _start_arguments(runs_dir))
    try:
        await_running(supervisor_dir)

        running = run_cli(["status"], supervisor_dir)
        assert running.returncode == ExitCode.OK
        assert running.stdout.startswith("running")
        assert "pid=" in running.stdout
        assert "since=" in running.stdout

        stopped = run_cli(["stop"], supervisor_dir)
        assert stopped.returncode == ExitCode.OK

        assert process.wait() == ExitCode.OK
        after = run_cli(["status"], supervisor_dir)
        assert after.returncode == ExitCode.NOT_RUNNING_STATUS
        assert after.stdout.strip() == "stopped"
    finally:
        process.cleanup()


def test_a_second_start_refuses_without_disturbing_the_first(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    """Single-instance enforcement, and the first process carries on."""
    process = start_background(supervisor_dir, _start_arguments(runs_dir))
    try:
        await_running(supervisor_dir)
        first_status = run_cli(["status"], supervisor_dir).stdout

        second = run_cli(["start", *_start_arguments(runs_dir)], supervisor_dir)

        assert second.returncode == ExitCode.ALREADY_RUNNING
        assert process.is_running(), "the first process must be undisturbed"
        assert run_cli(["status"], supervisor_dir).stdout == first_status
    finally:
        process.cleanup()


def test_stop_with_nothing_running(supervisor_dir: Path) -> None:
    """``stop`` against a stopped supervisor is a clear, typed refusal."""
    result = run_cli(["stop"], supervisor_dir)

    assert result.returncode == ExitCode.NOT_RUNNING
    assert "not running" in result.stderr


def test_stop_accepts_stop_timeout(supervisor_dir: Path) -> None:
    """``--stop-timeout`` is reachable on ``stop`` (review finding F001).

    Previously the flag was registered only on ``start``, so argparse rejected
    it here as an unrecognized argument. Asserting on ``NOT_RUNNING`` rather
    than ``FAILURE`` proves the flag itself parsed correctly and reached
    dispatch, not merely that *some* exit code came back.
    """
    result = run_cli(["stop", "--stop-timeout", "5"], supervisor_dir)

    assert result.returncode == ExitCode.NOT_RUNNING
    assert "unrecognized arguments" not in result.stderr


def test_start_no_longer_exposes_stop_timeout(supervisor_dir: Path) -> None:
    """``--stop-timeout`` moved off ``start``: it never used the value."""
    result = run_cli(["start", "--stop-timeout", "5"], supervisor_dir)

    assert result.returncode != ExitCode.OK
    assert "unrecognized arguments" in result.stderr


def test_status_with_nothing_ever_started(supervisor_dir: Path) -> None:
    """A supervisor directory that has never run reports stopped."""
    result = run_cli(["status"], supervisor_dir)

    assert result.returncode == ExitCode.NOT_RUNNING_STATUS
    assert result.stdout.strip() == "stopped"


# --------------------------------------------------------------------------
# Crash-only
# --------------------------------------------------------------------------


def test_kill_nine_then_start_needs_no_cleanup(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    """The slice's own claim: kill -9 then start, with no manual cleanup.

    Between the two, ``status`` reports the stale pid file rather than
    claiming the supervisor is running.
    """
    victim = start_background(supervisor_dir, _start_arguments(runs_dir))
    try:
        await_running(supervisor_dir)
        victim.kill_and_wait()
    finally:
        victim.cleanup()

    # A killed process cleans up nothing, so the pid file is still there.
    assert (supervisor_dir / "amoeba.pid").exists()

    between = run_cli(["status"], supervisor_dir)
    assert between.returncode == ExitCode.NOT_RUNNING_STATUS
    assert between.stdout.strip() == "stopped (stale pid file)"

    survivor = start_background(supervisor_dir, _start_arguments(runs_dir))
    try:
        await_running(supervisor_dir)
        assert run_cli(["stop"], supervisor_dir).returncode == ExitCode.OK
        assert survivor.wait() == ExitCode.OK
    finally:
        survivor.cleanup()


def test_lock_held_with_no_pid_file(supervisor_dir: Path, runs_dir: Path) -> None:
    """``running (pid unknown)`` and ``NO_STOP_TARGET``, signalling nothing.

    The start sequence takes the lock before writing the PID file, so a live
    process can legitimately be in this state. Removing the file reproduces it
    without racing the start sequence.
    """
    process = start_background(supervisor_dir, _start_arguments(runs_dir))
    try:
        await_running(supervisor_dir)
        (supervisor_dir / "amoeba.pid").unlink()

        status = run_cli(["status"], supervisor_dir)
        assert status.returncode == ExitCode.OK
        assert status.stdout.strip() == "running (pid unknown)"

        stop = run_cli(["stop"], supervisor_dir)
        assert stop.returncode == ExitCode.NO_STOP_TARGET
        assert "amoeba.lock" in stop.stderr
        assert "Nothing was signalled" in stop.stderr

        # The process really was left alone.
        assert process.is_running()
    finally:
        process.cleanup()


@pytest.mark.parametrize("corrupt", ["", "{truncated", "[1,2,3]"])
def test_a_corrupt_pid_file_presents_as_pid_unknown(
    supervisor_dir: Path, runs_dir: Path, corrupt: str
) -> None:
    """A truncated or malformed PID file reads exactly like an absent one."""
    process = start_background(supervisor_dir, _start_arguments(runs_dir))
    try:
        await_running(supervisor_dir)
        (supervisor_dir / "amoeba.pid").write_text(corrupt, encoding="utf-8")

        assert (
            run_cli(["status"], supervisor_dir).stdout.strip()
            == "running (pid unknown)"
        )
        assert run_cli(["stop"], supervisor_dir).returncode == ExitCode.NO_STOP_TARGET
    finally:
        process.cleanup()


def test_stop_never_escalates_to_sigkill(supervisor_dir: Path) -> None:
    """No SIGKILL is *sent* anywhere in the lifecycle code.

    Asserted against the parsed source rather than by observing behavior: the
    absence of an escalation is hard to prove by running the thing, and easy
    to prove by reading it. The AST walk is what keeps the module's own prose
    — which explains that it never escalates — from tripping the check, the
    way a plain substring search would.
    """
    import ast

    import amoeba.cli.lifecycle as lifecycle_module

    tree = ast.parse(Path(lifecycle_module.__file__).read_text(encoding="utf-8"))
    referenced = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    } | {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    assert "SIGKILL" not in referenced
    assert "SIGTERM" in referenced


# --------------------------------------------------------------------------
# Migration on start
# --------------------------------------------------------------------------


def test_start_migrates_a_version_two_store_keeping_its_data(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    """The Integration Requirement: a slice-101 store upgrades in place.

    The store is staged at version 2 with a node and an open blocked state,
    exactly as slice 101 code would have left it.
    """
    project_store_file = supervisor_dir / f"{PROJECT}.sqlite3"
    connection = sqlite3.connect(project_store_file)
    try:
        migrate(connection, expected_version=2)
        connection.execute(
            "INSERT INTO nodes (id, project_id, parent_id, kind, status, title, "
            "created_at, updated_at) VALUES (?, ?, NULL, ?, ?, ?, ?, ?)",
            (
                "n1",
                PROJECT,
                "slice",
                "blocked_on_human",
                "survivor",
                "2026-09-17T00:00:00+00:00",
                "2026-09-17T00:00:00+00:00",
            ),
        )
        connection.execute(
            "INSERT INTO blocked_states (id, node_id, kind, context, created_at, "
            "updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "b1",
                "n1",
                "human",
                "waiting on the PM",
                "2026-09-17T00:00:00+00:00",
                "2026-09-17T00:00:00+00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    process = start_background(supervisor_dir, _start_arguments(runs_dir))
    try:
        await_running(supervisor_dir)
        assert run_cli(["stop"], supervisor_dir).returncode == ExitCode.OK
        process.wait()
    finally:
        process.cleanup()

    verifier = sqlite3.connect(project_store_file)
    try:
        assert read_schema_version(verifier) == EXPECTED_SCHEMA_VERSION
    finally:
        verifier.close()

    with Store.open_read_only(project_store_file) as store:
        nodes = store.nodes_for_project(PROJECT)
        blocked = store.blocked(PROJECT)

    assert [node.title for node in nodes] == ["survivor"]
    assert len(blocked) == 1
    assert blocked[0].blocked_state.context == "waiting on the PM"


def test_start_logs_a_recovery_summary_per_project(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    """The startup log accounts for every project, including empty ones."""
    for project_id in ("alpha", "beta"):
        with Store.open(supervisor_dir / f"{project_id}.sqlite3") as store:
            store.create_node(
                project_id=project_id, kind=NodeKind.SLICE, title="seeded"
            )

    process = start_background(supervisor_dir, _start_arguments(runs_dir))
    try:
        await_running(supervisor_dir)
        run_cli(["stop"], supervisor_dir)
        process.wait()
        output = process.output()
    finally:
        process.cleanup()

    assert "recovery alpha: nothing to reconcile" in output.stderr
    assert "recovery beta: nothing to reconcile" in output.stderr


def test_start_escalates_an_unresolved_entry_then_inspect_shows_it(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    """Recovery runs on start, and its results are visible through inspect."""
    project_store_file = supervisor_dir / f"{PROJECT}.sqlite3"
    with Store.open(project_store_file) as store:
        node = store.create_node(
            project_id=PROJECT, kind=NodeKind.SLICE, title="in-flight"
        )
        entry = store.journal_issue(
            node.id,
            kind=CommandKind.SQ_RUN,
            parameters={"pipeline": "p6", "params": {"slice": "102"}},
        )

    process = start_background(supervisor_dir, _start_arguments(runs_dir))
    try:
        await_running(supervisor_dir)

        blocked = run_cli(
            ["inspect", "blocked", "--project", PROJECT, "--json"], supervisor_dir
        )
        rows = json.loads(blocked.stdout)

        assert len(rows) == 1
        assert rows[0]["node_id"] == node.id
        assert entry.id in rows[0]["context"]

        run_cli(["stop"], supervisor_dir)
        process.wait()
    finally:
        process.cleanup()


def test_a_corrupt_store_fails_the_start(supervisor_dir: Path, runs_dir: Path) -> None:
    """One bad project stops the supervisor, with a typed exit code."""
    (supervisor_dir / "broken.sqlite3").write_bytes(b"not a sqlite database")

    result = run_cli(["start", *_start_arguments(runs_dir)], supervisor_dir)

    assert result.returncode == ExitCode.STARTUP_FAILED
    assert "broken" in result.stderr


def test_the_real_supervisor_directory_is_untouched(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    """A deliberate check that these tests operate only on tmp_path.

    The CLI resolves its directory from ``AMOEBA_STORE_DIR``, which the harness
    always overrides. This asserts the override actually takes effect, by
    confirming the files land where the test put them and that the resolved
    directory is inside pytest's temporary tree.
    """
    process = start_background(supervisor_dir, _start_arguments(runs_dir))
    try:
        await_running(supervisor_dir)

        assert (supervisor_dir / "amoeba.lock").exists()
        assert (supervisor_dir / "amoeba.pid").exists()

        contents = json.loads((supervisor_dir / "amoeba.pid").read_text())
        assert contents["pid"] == process.pid

        run_cli(["stop"], supervisor_dir)
        process.wait()
    finally:
        process.cleanup()

    await_stopped(supervisor_dir)


def test_blocked_listing_reflects_a_real_block(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    """Inspection reads what the store actually holds, while stopped."""
    project_store_file = supervisor_dir / f"{PROJECT}.sqlite3"
    with Store.open(project_store_file) as store:
        node = store.create_node(
            project_id=PROJECT, kind=NodeKind.GATE, title="awaiting review"
        )
        store.block(node.id, kind=BlockedKind.JUDGE, context="needs a verdict")

    result = run_cli(
        ["inspect", "blocked", "--project", PROJECT, "--json"], supervisor_dir
    )
    rows = json.loads(result.stdout)

    assert result.returncode == ExitCode.OK
    assert len(rows) == 1
    assert rows[0]["blocked_on"] == "judge"
    assert rows[0]["context"] == "needs a verdict"
