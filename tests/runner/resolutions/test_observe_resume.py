"""Observing a resume: confirmed by run state, failed by exit code or grace (D6)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from amoeba.process import RunCheckpoint, RunOutcome, RunOutcomeDocument
from amoeba.runner.decide import RunState
from amoeba.runner.faults import ResumeFailure
from amoeba.runner.observe_resume import resumed_from_states
from amoeba.runner.observed import ResumeFailed, RunEnded
from amoeba.runner.resolutions.confirm import ResumedFrom
from amoeba.store import PARAM_CONTINUATION, PARAM_CONTINUES, JournalEntry, Store
from runner.observe_support import GRACE, INTERVAL, Child, Rig, document, entry
from runner.resolutions.resolution_support import (
    design_step,
    finished_run,
    paused_document,
)

OLD = datetime(2026, 10, 23, 11, 0, tzinfo=UTC)
NEW = OLD + timedelta(minutes=45)


def _resume_entry(continuation: str = "retry") -> JournalEntry:
    base = entry()
    parameters = {
        **base.parameters,
        PARAM_CONTINUATION: continuation,
        PARAM_CONTINUES: "entry-0",
    }
    return replace(base, parameters=parameters)


def _paused(paused_at: datetime = OLD) -> RunOutcomeDocument:
    return RunOutcomeDocument(
        run_id="run-1",
        outcome=RunOutcome.PAUSED,
        checkpoint=RunCheckpoint(paused_at=paused_at),
    )


def _rig(tmp_path: Path, *polls: RunOutcomeDocument) -> tuple[Rig, JournalEntry]:
    rig = Rig(tmp_path, *polls)
    resume = _resume_entry()
    rig.resumed_from[resume.id] = ResumedFrom(RunOutcome.PAUSED, paused_at=OLD)
    return rig, resume


def test_a_run_that_stays_paused_then_claims_is_confirmed_by_the_first_poll_after(
    tmp_path: Path,
) -> None:
    rig, resume = _rig(tmp_path, _paused(), document("run-1", RunOutcome.TIMED_OUT))
    rig.tracker.track(resume.id, Child(None))

    first = rig.observe(resume)
    assert first.runs[0].run.state is RunState.LAUNCHING
    tracked = rig.tracker.get(resume.id)
    assert tracked is not None and not tracked.confirmed

    rig.clock.seconds = INTERVAL
    second = rig.observe(resume)

    assert second.runs[0].run.state is RunState.RUNNING
    assert tracked.confirmed


def test_a_new_paused_at_ends_the_run_as_a_pause(tmp_path: Path) -> None:
    rig, resume = _rig(tmp_path, _paused(NEW))
    rig.tracker.track(resume.id, Child(None))

    observed = rig.observe(resume)

    finished = observed.runs[0].finished
    assert isinstance(finished, RunEnded)
    assert finished.document.outcome is RunOutcome.PAUSED


@pytest.mark.parametrize(
    ("exit_code", "failure"),
    [(2, ResumeFailure.REFUSED), (1, ResumeFailure.EXITED_BEFORE_CLAIM)],
)
def test_a_child_that_exits_at_the_old_pause_fails_the_resume(
    tmp_path: Path, exit_code: int, failure: ResumeFailure
) -> None:
    # The second answer is the look taken again before the resume is called failed.
    rig, resume = _rig(tmp_path, _paused(), _paused())
    rig.tracker.track(resume.id, Child(exit_code))

    observed = rig.observe(resume)

    finished = observed.runs[0].finished
    assert isinstance(finished, ResumeFailed)
    assert (finished.failure, finished.exit_code) == (failure, exit_code)
    assert finished.document is not None


@pytest.mark.parametrize("exit_code", [1, 2])
def test_a_refused_resume_of_a_run_that_is_running_after_all_is_not_a_failure(
    tmp_path: Path, exit_code: int
) -> None:
    """Squadron refuses to resume a live run; the second look sees it running."""
    rig, resume = _rig(tmp_path, _paused(), document("run-1", RunOutcome.TIMED_OUT))
    rig.tracker.track(resume.id, Child(exit_code))

    observed = rig.observe(resume)

    assert observed.runs[0].finished is None
    assert observed.runs[0].run.state is RunState.RUNNING


def test_a_resume_from_a_failed_run_is_confirmed_by_a_later_updated_at(
    tmp_path: Path,
) -> None:
    rig = Rig(
        tmp_path,
        RunOutcomeDocument(
            run_id="run-1",
            outcome=RunOutcome.FAILED,
            updated_at=OLD + timedelta(minutes=5),
        ),
    )
    resume = _resume_entry()
    rig.resumed_from[resume.id] = ResumedFrom(RunOutcome.FAILED, OLD)
    rig.tracker.track(resume.id, Child(None))

    observed = rig.observe(resume)

    finished = observed.runs[0].finished
    assert isinstance(finished, RunEnded)
    assert finished.document.outcome is RunOutcome.FAILED


def test_a_resume_from_an_orphaned_run_is_still_resuming_while_the_old_state_shows(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path, RunOutcomeDocument(run_id="run-1", outcome=RunOutcome.ORPHANED))
    resume = _resume_entry()
    rig.resumed_from[resume.id] = ResumedFrom(RunOutcome.ORPHANED)
    rig.tracker.track(resume.id, Child(None))

    observed = rig.observe(resume)

    assert observed.runs[0].finished is None
    assert observed.runs[0].run.state is RunState.LAUNCHING


def test_no_claim_within_grace_fails_a_running_child(tmp_path: Path) -> None:
    rig, resume = _rig(tmp_path, _paused())
    rig.tracker.track(resume.id, Child(None))
    rig.clock.seconds = GRACE + 1

    observed = rig.observe(resume)

    finished = observed.runs[0].finished
    assert isinstance(finished, ResumeFailed)
    assert finished.failure is ResumeFailure.NO_CLAIM_WITHIN_GRACE


def test_a_missing_run_fails_the_resume(tmp_path: Path) -> None:
    rig, resume = _rig(tmp_path, document("run-1", RunOutcome.NOT_FOUND))
    rig.tracker.track(resume.id, Child(None))

    observed = rig.observe(resume)

    finished = observed.runs[0].finished
    assert isinstance(finished, ResumeFailed)
    assert finished.failure is ResumeFailure.RUN_MISSING


def test_with_no_tracked_child_only_the_grace_rule_applies(tmp_path: Path) -> None:
    rig, resume = _rig(tmp_path, _paused(), _paused())

    inside = rig.observe(resume)
    assert inside.runs[0].run.state is RunState.LAUNCHING

    rig.clock.seconds = GRACE + 1
    past = rig.observe(resume)
    finished = past.runs[0].finished
    assert isinstance(finished, ResumeFailed)
    assert finished.failure is ResumeFailure.NO_CLAIM_WITHIN_GRACE
    assert finished.exit_code is None


def test_with_no_tracked_child_a_claimed_run_is_still_confirmed(
    tmp_path: Path,
) -> None:
    rig, resume = _rig(tmp_path, document("run-1", RunOutcome.TIMED_OUT))

    observed = rig.observe(resume)

    assert observed.runs[0].run.state is RunState.RUNNING


def test_a_resume_whose_pause_could_not_be_read_cannot_be_confirmed(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path, _paused(NEW))
    resume = _resume_entry()
    rig.resumed_from[resume.id] = None
    rig.tracker.track(resume.id, Child(None))

    observed = rig.observe(resume)

    assert observed.runs[0].run.state is RunState.LAUNCHING


def test_an_observe_continuation_takes_the_confirmed_path_unchanged(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path, _paused())
    handled = _resume_entry("observe")

    observed = rig.observe(handled)

    assert isinstance(observed.runs[0].finished, RunEnded)


def test_the_mapping_comes_from_the_continued_entries(store: Store) -> None:
    node = design_step(store)
    paused = finished_run(
        store, node, RunOutcome.PAUSED, document=paused_document("r1")
    )
    unparseable = finished_run(
        store, node, RunOutcome.PAUSED, document={"run_id": "r", "outcome": "nope"}
    )
    other = design_step(store)

    def resume_of(continues: str, node_id: str) -> JournalEntry:
        return replace(
            _resume_entry(),
            id=f"resume-{continues[:6]}",
            node_id=node_id,
            parameters={
                PARAM_CONTINUATION: "retry",
                PARAM_CONTINUES: continues,
            },
        )

    entries = [
        resume_of(paused.id, node.id),
        resume_of(unparseable.id, node.id),
        resume_of("missing-entry", other.id),
        _resume_entry("observe"),
    ]

    pauses = resumed_from_states(store, entries)

    origin = pauses[entries[0].id]
    assert origin is not None and origin.paused_at == datetime(
        2026, 10, 25, 12, 0, tzinfo=UTC
    )
    assert pauses[entries[1].id] is None
    assert pauses[entries[2].id] is None
    assert entries[3].id not in pauses
