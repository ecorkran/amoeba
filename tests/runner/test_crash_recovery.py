"""SIGKILL the Runner at each point of a launch; restart; the end state is right.

Slice 122, Verification Walkthrough step 2. Every wait is on a condition, never a
fixed sleep. After the restart the stub's call log gives the ``sq run`` count for
the run id.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from contract.launched import LaunchedProcess

from amoeba.store import JournalOutcome, JournalResolver
from runner.crash_entry import KillPoint
from runner.crash_harness import CrashHarness, RunSettings


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[CrashHarness]:
    created = CrashHarness(tmp_path)
    yield created
    created.close()


def _crash_and_restart(
    harness: CrashHarness, run: RunSettings, kill_at: KillPoint
) -> tuple[str, LaunchedProcess]:
    """Start armed, wait for the SIGKILL, restart unarmed. Returns (run id, process)."""
    first = harness.start(run, kill_at)
    harness.wait_for_sigkill(first)
    [journaled] = harness.entries()
    assert not journaled.is_resolved, "the crash left the entry open"
    second = harness.start(run)
    return str(journaled.parameters["run_id"]), second


def test_kill_before_launch_is_not_applied_and_not_relaunched(
    harness: CrashHarness,
) -> None:
    run_id, process = _crash_and_restart(
        harness, RunSettings(run_seconds=0.2), KillPoint.BEFORE_LAUNCH
    )

    entry = harness.wait_for_resolution()

    assert (entry.outcome, entry.resolved_by) == (
        JournalOutcome.NOT_APPLIED,
        JournalResolver.RECOVERY,
    )
    assert harness.sq_run_calls(run_id) == 0
    assert harness.all_sq_run_calls() == 0, "no relaunch under any id"
    assert harness.open_blocks(entry.node_id) == []
    harness.stop(process)
    assert harness.all_sq_run_calls() == 0


def test_kill_while_running_is_recorded_after_restart(harness: CrashHarness) -> None:
    run_id, process = _crash_and_restart(
        harness, RunSettings(run_seconds=3.0), KillPoint.WHILE_RUNNING
    )

    entry = harness.wait_for_resolution()

    assert (entry.outcome, entry.resolved_by) == (
        JournalOutcome.COMPLETED,
        JournalResolver.ISSUER,
    )
    assert entry.result is not None
    assert entry.result["run_id"] == run_id and entry.result["outcome"] == "completed"
    assert harness.sq_run_calls(run_id) == 1
    assert harness.open_blocks(entry.node_id) == []
    harness.stop(process)


def test_kill_after_finish_before_record_is_recorded_on_first_tick(
    harness: CrashHarness,
) -> None:
    run_id, process = _crash_and_restart(
        harness, RunSettings(run_seconds=0.2), KillPoint.AFTER_FINISH
    )

    entry = harness.wait_for_resolution()

    assert (entry.outcome, entry.resolved_by) == (
        JournalOutcome.COMPLETED,
        JournalResolver.ISSUER,
    )
    assert entry.result is not None and entry.result["outcome"] == "completed"
    assert harness.sq_run_calls(run_id) == 1
    harness.stop(process)


def test_kill_between_block_and_resolve_finishes_the_sequence(
    harness: CrashHarness,
) -> None:
    run_id, process = _crash_and_restart(
        harness,
        RunSettings(run_seconds=0.2, outcome="failed"),
        KillPoint.BETWEEN_BLOCK_AND_RESOLVE,
    )
    [journaled] = harness.entries()
    assert len(harness.open_blocks(journaled.node_id)) == 1, "blocked before the kill"

    entry = harness.wait_for_resolution()

    assert entry.outcome is JournalOutcome.COMPLETED
    assert entry.result is not None and entry.result["outcome"] == "failed"
    assert len(harness.open_blocks(entry.node_id)) == 1, "one blocked state, not two"
    assert harness.sq_run_calls(run_id) == 1
    harness.stop(process)
