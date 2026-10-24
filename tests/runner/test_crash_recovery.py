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
from sq_stub import write_run_script
from sq_stub_scripts import RunScript, single_review, split_review

from amoeba.runner.finish import RESULT_RUN_ID
from amoeba.store import PARAM_RUN_ID, JournalOutcome, JournalResolver
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
    return str(journaled.parameters[PARAM_RUN_ID]), second


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
    assert (
        entry.result[RESULT_RUN_ID] == run_id and entry.result["outcome"] == "completed"
    )
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


# --------------------------------------------------------------------------
# Ingestion (slice 125): the reviews a run wrote, and routing after
# --------------------------------------------------------------------------

REVIEW_SLICE = "crash-proof-slice"


@pytest.fixture
def review_harness(tmp_path: Path) -> Iterator[CrashHarness]:
    created = CrashHarness(tmp_path, slice_name=REVIEW_SLICE)
    yield created
    created.close()


def _review_run(
    harness: CrashHarness, script: RunScript, outcome: str = "completed"
) -> RunSettings:
    path = write_run_script(
        harness.tmp_path / "run-script.json",
        files=script.files,
        document=script.document,
    )
    return RunSettings(run_seconds=0.2, outcome=outcome, script=path)


def test_kill_between_block_and_report_finishes_once(
    review_harness: CrashHarness,
) -> None:
    split = split_review(REVIEW_SLICE)
    script = RunScript(split.files, {**split.document, "failure": {"kind": "stall"}})
    run = _review_run(review_harness, script, "failed")

    first = review_harness.start(run, KillPoint.BETWEEN_BLOCK_AND_REPORT)
    review_harness.wait_for_sigkill(first)
    [journaled] = review_harness.entries()
    assert not journaled.is_resolved, "the crash left the entry open"
    assert len(review_harness.open_blocks(journaled.node_id)) == 1, "blocked first"
    assert review_harness.verdict_ids() == [], "nothing recorded before the kill"
    run_id = str(journaled.parameters[PARAM_RUN_ID])
    process = review_harness.start(run)

    entry = review_harness.wait_for_resolution()

    assert entry.outcome is JournalOutcome.COMPLETED
    assert len(review_harness.open_blocks(entry.node_id)) == 1, "one blocked state"
    verdict_ids = review_harness.verdict_ids()
    assert len(verdict_ids) == 2 and len(set(verdict_ids)) == 2, "once per part"
    assert review_harness.sq_run_calls(run_id) == 1
    review_harness.stop(process)


def test_kill_between_ingest_and_route_keeps_outcome_unrouted(
    review_harness: CrashHarness,
) -> None:
    run = _review_run(review_harness, single_review(REVIEW_SLICE))
    first = review_harness.start(run, KillPoint.AFTER_INGEST)
    review_harness.wait_for_sigkill(first)
    [entry] = review_harness.entries()
    assert entry.is_resolved and entry.awaits_routing, "ingested before the kill"
    assert [e.id for e in review_harness.unrouted()] == [entry.id]

    second = review_harness.start(run)
    review_harness.stop(second)

    assert [e.id for e in review_harness.unrouted()] == [entry.id], "still unrouted"
    assert len(review_harness.verdict_ids()) == 1, "recorded once, not again"
    review_harness.route(entry)
    assert review_harness.unrouted() == []
