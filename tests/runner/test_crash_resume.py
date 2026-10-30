"""SIGKILL the Runner around a resume; restart; the resume happens at most once.

Slice 127, Verification Walkthrough. The stub ``sq`` keeps a paused run and logs every
call, so the proof is what it was asked: one ``--resume`` after a kill before the
journal write, and none after a kill between the journal write and the launch.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.store import (
    PARAM_CONTINUATION,
    JournalEntry,
    JournalOutcome,
    NodeStatus,
    ResolutionOutcome,
    Store,
    project_store_path,
)
from runner.crash_entry import KillPoint
from runner.crash_harness import PROJECT, CrashHarness, RunSettings
from runner.crash_resume import (
    StagedResume,
    stage_paused_retry,
    stage_transient_failure,
)


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[CrashHarness]:
    created = CrashHarness(tmp_path, dispatch=True)
    yield created
    created.close()


def _resume_calls(harness: CrashHarness) -> int:
    if not harness.sq_log.exists():
        return 0
    lines = harness.sq_log.read_text().splitlines()
    return sum(1 for line in lines if line.startswith("run --resume"))


def _continuations(harness: CrashHarness) -> list[JournalEntry]:
    return [e for e in harness.entries() if PARAM_CONTINUATION in e.parameters]


def _answer(harness: CrashHarness, staged: StagedResume) -> ResolutionOutcome | None:
    with Store.open_read_only(project_store_path(harness.supervisor_dir, PROJECT)) as s:
        state = s.blocked_state(staged.blocked_state_id)
    assert state is not None
    return state.runner_outcome


def test_kill_after_acknowledgment_resumes_once_after_restart(
    harness: CrashHarness,
) -> None:
    staged = stage_paused_retry(harness)
    run = RunSettings(run_seconds=0.2)

    first = harness.start(run, KillPoint.AFTER_ACKNOWLEDGE)
    harness.wait_for_sigkill(first)

    assert _answer(harness, staged) is ResolutionOutcome.APPLIED, "durable answer"
    assert _continuations(harness) == [], "nothing journaled before the kill"
    assert _resume_calls(harness) == 0

    second = harness.start(run)
    harness.wait_until(
        "the resumed run to be recorded",
        lambda: any(e.is_resolved for e in _continuations(harness)),
    )
    harness.stop(second)

    [continuation] = _continuations(harness)
    assert continuation.outcome is JournalOutcome.COMPLETED
    assert continuation.parameters[PARAM_CONTINUATION] == "retry"
    assert _resume_calls(harness) == 1, "issued once, not again"


def test_kill_after_the_resume_is_journaled_is_never_launched(
    harness: CrashHarness,
) -> None:
    staged = stage_paused_retry(harness)
    run = RunSettings(run_seconds=0.2)

    first = harness.start(run, KillPoint.BEFORE_RESUME_LAUNCH)
    harness.wait_for_sigkill(first)

    [journaled] = _continuations(harness)
    assert not journaled.is_resolved, "the crash left the resume open"
    assert _resume_calls(harness) == 0

    second = harness.start(run)
    harness.wait_until(
        "the resume to fail with no claim",
        lambda: any(e.is_resolved for e in _continuations(harness)),
    )
    harness.stop(second)

    [failed] = _continuations(harness)
    assert failed.outcome is JournalOutcome.FAILED
    assert failed.result is not None
    assert failed.result["resume_failure"] == "no_claim_within_grace"
    assert _resume_calls(harness) == 0, "recovery never launches a resume"
    assert harness.node(staged.node_id).status is NodeStatus.BLOCKED_ON_HUMAN


def _transient_resumes(harness: CrashHarness) -> list[JournalEntry]:
    return [
        e
        for e in _continuations(harness)
        if e.parameters.get("resume_cause") == "transient"
    ]


def test_kill_after_an_automatic_resume_is_journaled_never_issues_a_second(
    harness: CrashHarness,
) -> None:
    staged = stage_transient_failure(harness)
    run = RunSettings(run_seconds=0.2)

    first = harness.start(run, KillPoint.BEFORE_RESUME_LAUNCH)
    harness.wait_for_sigkill(first)

    [journaled] = _transient_resumes(harness)
    assert not journaled.is_resolved, "the crash left the resume open"
    assert _resume_calls(harness) == 0

    second = harness.start(run)
    harness.wait_until(
        "the resume to fail with no claim",
        lambda: any(e.is_resolved for e in _transient_resumes(harness)),
    )
    harness.stop(second)

    [failed] = _transient_resumes(harness)
    assert failed.id == journaled.id, "the same resume, never a second one"
    assert failed.result is not None
    assert failed.result["resume_failure"] == "no_claim_within_grace"
    assert _resume_calls(harness) == 0, "recovery never launches a resume"
    assert harness.node(staged.node_id).status is NodeStatus.BLOCKED_ON_HUMAN
