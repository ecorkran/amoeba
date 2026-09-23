"""InboxTenant inside a real, running ``amoeba start``.

What only a real process can show: submissions made while it is stopped,
runtime project creation without a restart, the crash-table row between store
creation and the record commit, and the attempt counter surviving real
restarts until the park keeps the process up. Branch coverage of the tenant
itself lives in ``test_inbox_tenant.py``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest
from cli_harness import await_running, run_cli, start_background

from amoeba.cli.main import ExitCode
from amoeba.inbox import failed, pending, quarantined, submit
from amoeba.store import NodeKind, Store, SubmissionKind, SubmissionOutcome
from amoeba.store.inbox_models import INTENT_BODY
from amoeba.store.paths import STORE_FILE_SUFFIX

PROJECT = "demo"

#: Generous, like the CLI harness's own: a loaded machine must not flake it.
APPLY_TIMEOUT_SECONDS = 20.0


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """A throwaway supervisor directory that exists. Never the real one."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    """An empty Squadron runs directory. Never the real one."""
    directory = tmp_path / "runs"
    directory.mkdir()
    return directory


def _start_arguments(runs_dir: Path, *extra: str) -> list[str]:
    return ["--sq-runs-dir", str(runs_dir), "--idle-interval", "0.05", *extra]


def _store_file(supervisor_dir: Path, project_id: str) -> Path:
    return supervisor_dir / f"{project_id}{STORE_FILE_SUFFIX}"


def _seed(supervisor_dir: Path, project_id: str = PROJECT) -> None:
    with Store.open(_store_file(supervisor_dir, project_id)) as store:
        store.create_node(project_id=project_id, kind=NodeKind.SLICE, title="seeded")


def _submit(supervisor_dir: Path, project_id: str, kind: SubmissionKind) -> str:
    payload: dict[str, object] = (
        {INTENT_BODY: {"want": "x"}} if kind is SubmissionKind.INTENT else {}
    )
    return submit(
        project_id=project_id,
        kind=kind,
        payload=payload,
        submitted_by="tester",
        store_dir=supervisor_dir,
    )


def _outcome(
    supervisor_dir: Path, project_id: str, submission_id: str
) -> SubmissionOutcome | None:
    path = _store_file(supervisor_dir, project_id)
    if not path.is_file():
        return None
    with Store.open_read_only(path) as store:
        record = store.submission(submission_id)
    return None if record is None else record.outcome


def _await(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + APPLY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError(f"{what} did not happen within {APPLY_TIMEOUT_SECONDS}s")


def _await_applied(supervisor_dir: Path, project_id: str, submission_id: str) -> None:
    _await(
        lambda: (
            _outcome(supervisor_dir, project_id, submission_id)
            is SubmissionOutcome.APPLIED
        ),
        f"submission {submission_id} for {project_id}",
    )


def _stop(supervisor_dir: Path) -> None:
    assert run_cli(["stop"], supervisor_dir).returncode == ExitCode.OK


# --------------------------------------------------------------------------
# Applying through a running process
# --------------------------------------------------------------------------


def test_a_submission_made_while_stopped_applies_on_start(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    _seed(supervisor_dir)
    submission_id = _submit(supervisor_dir, PROJECT, SubmissionKind.INTENT)

    process = start_background(supervisor_dir, _start_arguments(runs_dir))
    try:
        await_running(supervisor_dir)
        _await_applied(supervisor_dir, PROJECT, submission_id)
        _stop(supervisor_dir)
        assert process.wait() == ExitCode.OK
    finally:
        process.cleanup()

    assert pending(supervisor_dir) == []


def test_a_file_dropped_into_a_running_process_is_applied(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    _seed(supervisor_dir)
    process = start_background(supervisor_dir, _start_arguments(runs_dir))
    try:
        await_running(supervisor_dir)
        submission_id = _submit(supervisor_dir, PROJECT, SubmissionKind.INTENT)
        _await_applied(supervisor_dir, PROJECT, submission_id)
        _stop(supervisor_dir)
    finally:
        process.cleanup()


def test_runtime_creation_serves_later_submissions_without_a_restart(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    """Created and used in one tick, and in a later one, with no restart."""
    create_early = _submit(supervisor_dir, "early", SubmissionKind.CREATE_PROJECT)
    intent_same_tick = _submit(supervisor_dir, "early", SubmissionKind.INTENT)

    process = start_background(supervisor_dir, _start_arguments(runs_dir))
    try:
        await_running(supervisor_dir)
        _await_applied(supervisor_dir, "early", intent_same_tick)
        intent_later_tick = _submit(supervisor_dir, "early", SubmissionKind.INTENT)
        _await_applied(supervisor_dir, "early", intent_later_tick)

        create_late = _submit(supervisor_dir, "late", SubmissionKind.CREATE_PROJECT)
        intent_late = _submit(supervisor_dir, "late", SubmissionKind.INTENT)
        _await_applied(supervisor_dir, "late", intent_late)
        _stop(supervisor_dir)
    finally:
        process.cleanup()

    assert _outcome(supervisor_dir, "early", create_early) is SubmissionOutcome.APPLIED
    assert _outcome(supervisor_dir, "late", create_late) is SubmissionOutcome.APPLIED
    assert quarantined(supervisor_dir) == []


def test_killed_between_store_creation_and_record_commit(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    """The crash-table row no other test reaches.

    The store exists (as ``open_project`` left it) with no record, and the
    ``create_project`` file is still in ``new/``. On restart the store is
    discovered, ``open_project`` finds it open, and the record is written —
    exactly once, across a further restart too.
    """
    Store.open(_store_file(supervisor_dir, "half-made")).close()
    submission_id = _submit(supervisor_dir, "half-made", SubmissionKind.CREATE_PROJECT)

    for _ in range(2):
        process = start_background(supervisor_dir, _start_arguments(runs_dir))
        try:
            await_running(supervisor_dir)
            _await_applied(supervisor_dir, "half-made", submission_id)
            _stop(supervisor_dir)
        finally:
            process.cleanup()

    with Store.open_read_only(_store_file(supervisor_dir, "half-made")) as store:
        assert [record.id for record in store.submissions("half-made")] == [
            submission_id
        ]
    assert pending(supervisor_dir) == []


# --------------------------------------------------------------------------
# F001: a sick store across real restarts
# --------------------------------------------------------------------------


def test_a_sick_store_stops_each_start_until_parked_then_the_process_stays_up(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    # A directory where the store file belongs: not discovered at start, and
    # every open_project for it fails the same way.
    _store_file(supervisor_dir, "sick").mkdir()
    _submit(supervisor_dir, "sick", SubmissionKind.CREATE_PROJECT)
    healthy = _submit(supervisor_dir, "healthy", SubmissionKind.CREATE_PROJECT)
    arguments = ["start", *_start_arguments(runs_dir, "--inbox-max-attempts", "3")]

    # The first max_attempts - 1 starts stop, and the count survives each one.
    # The exit status is not pinned: the boundary maps any StoreError to
    # STARTUP_FAILED, a label that reads oddly for a failure mid-run.
    for expected in (1, 2):
        stopped = run_cli(arguments, supervisor_dir)
        assert stopped.returncode != ExitCode.OK
        assert f"attempt {expected} of 3" in stopped.stderr
        assert [entry.attempts for entry in pending(supervisor_dir)] == [expected, 0]

    # The third parks it, applies the next file, and keeps running.
    process = start_background(supervisor_dir, arguments[1:])
    try:
        await_running(supervisor_dir)
        _await_applied(supervisor_dir, "healthy", healthy)
        assert process.is_running()
        _stop(supervisor_dir)
        assert process.wait() == ExitCode.OK
        stderr = process.output().stderr
    finally:
        process.cleanup()

    [parked] = failed(supervisor_dir)
    assert parked.attempts == 3
    assert parked.last_error is not None
    assert parked.last_error.startswith("StorePermissionError")
    assert "ERROR" in stderr and "parked" in stderr
    assert quarantined(supervisor_dir) == []
    assert pending(supervisor_dir) == []
