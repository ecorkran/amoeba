"""``resume_progress``: every row of D6's confirmation and failure table."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from amoeba.process import RunCheckpoint, RunOutcome, RunOutcomeDocument
from amoeba.runner.faults import ResumeFailure
from amoeba.runner.resolutions.confirm import (
    CONFIRMED,
    STILL_RESUMING,
    ResumedFrom,
    resume_progress,
    resumed_from_entry,
)
from amoeba.store import CommandKind, JournalEntry

OLD_AT = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)
NEW = OLD_AT + timedelta(hours=1)
OLD = ResumedFrom(RunOutcome.PAUSED, paused_at=OLD_AT)


def _poll(outcome: RunOutcome, paused_at: datetime | None = None) -> RunOutcomeDocument:
    checkpoint = None if paused_at is None else RunCheckpoint(paused_at=paused_at)
    return RunOutcomeDocument(run_id="r", outcome=outcome, checkpoint=checkpoint)


@pytest.mark.parametrize(
    "outcome",
    [
        RunOutcome.COMPLETED,
        RunOutcome.FAILED,
        RunOutcome.TIMED_OUT,
        RunOutcome.ORPHANED,
        RunOutcome.UNREADABLE,
    ],
)
def test_any_outcome_other_than_paused_confirms(outcome: RunOutcome) -> None:
    assert resume_progress(_poll(outcome), OLD, None, False) == CONFIRMED


def test_timed_out_confirms_even_with_no_child_and_past_grace() -> None:
    assert resume_progress(_poll(RunOutcome.TIMED_OUT), OLD, None, True) == CONFIRMED


def test_retry_confirmed_by_new_paused_at() -> None:
    assert resume_progress(_poll(RunOutcome.PAUSED, NEW), OLD, None, False) == CONFIRMED


def test_a_new_pause_confirms_even_if_the_child_exited_two() -> None:
    assert resume_progress(_poll(RunOutcome.PAUSED, NEW), OLD, 2, True) == CONFIRMED


def test_the_old_pause_with_a_running_child_inside_grace_is_still_resuming() -> None:
    assert (
        resume_progress(_poll(RunOutcome.PAUSED, OLD_AT), OLD, None, False)
        == STILL_RESUMING
    )


def test_a_missing_run_is_run_missing() -> None:
    result = resume_progress(_poll(RunOutcome.NOT_FOUND), OLD, None, False)

    assert result is ResumeFailure.RUN_MISSING


def test_exit_two_at_the_old_pause_is_refused() -> None:
    result = resume_progress(_poll(RunOutcome.PAUSED, OLD_AT), OLD, 2, False)

    assert result is ResumeFailure.REFUSED


@pytest.mark.parametrize("code", [0, 1, 3, 137])
def test_another_exit_code_at_the_old_pause_exited_before_claim(code: int) -> None:
    result = resume_progress(_poll(RunOutcome.PAUSED, OLD_AT), OLD, code, False)

    assert result is ResumeFailure.EXITED_BEFORE_CLAIM


@pytest.mark.parametrize("exit_code", [None])
def test_no_claim_within_grace_with_a_running_or_untracked_child(
    exit_code: int | None,
) -> None:
    result = resume_progress(_poll(RunOutcome.PAUSED, OLD_AT), OLD, exit_code, True)

    assert result is ResumeFailure.NO_CLAIM_WITHIN_GRACE


def test_an_unknown_resumed_from_never_confirms_a_pause() -> None:
    inside = resume_progress(_poll(RunOutcome.PAUSED, NEW), None, None, False)
    past = resume_progress(_poll(RunOutcome.PAUSED, NEW), None, None, True)

    assert inside == STILL_RESUMING
    assert past is ResumeFailure.NO_CLAIM_WITHIN_GRACE


def test_a_pause_with_no_paused_at_cannot_be_judged_new() -> None:
    result = resume_progress(_poll(RunOutcome.PAUSED), OLD, None, True)

    assert result is ResumeFailure.NO_CLAIM_WITHIN_GRACE


# -- slice 132, D5: resumes from a failed or orphaned run ------------------------

SAW = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)
LATER = SAW + timedelta(minutes=1)


def _doc(outcome: RunOutcome, updated_at: datetime | None) -> RunOutcomeDocument:
    return RunOutcomeDocument(run_id="r", outcome=outcome, updated_at=updated_at)


@pytest.mark.parametrize("stopped", [RunOutcome.FAILED, RunOutcome.ORPHANED])
def test_a_resume_from_a_stopped_run_is_confirmed_by_a_later_updated_at(
    stopped: RunOutcome,
) -> None:
    origin = ResumedFrom(stopped, SAW)

    result = resume_progress(_doc(stopped, LATER), origin, None, False)

    assert result == CONFIRMED


@pytest.mark.parametrize("stopped", [RunOutcome.FAILED, RunOutcome.ORPHANED])
def test_the_old_failed_or_orphaned_state_is_still_resuming(
    stopped: RunOutcome,
) -> None:
    origin = ResumedFrom(stopped, SAW)

    result = resume_progress(_doc(stopped, SAW), origin, None, False)

    assert result == STILL_RESUMING


@pytest.mark.parametrize("stopped", [RunOutcome.FAILED, RunOutcome.ORPHANED])
def test_a_running_run_confirms_a_resume_from_a_stopped_run(
    stopped: RunOutcome,
) -> None:
    origin = ResumedFrom(stopped, SAW)

    assert (
        resume_progress(_doc(RunOutcome.TIMED_OUT, SAW), origin, 1, True) == CONFIRMED
    )


def test_the_old_failed_state_with_an_exited_child_failed_the_resume() -> None:
    origin = ResumedFrom(RunOutcome.FAILED, SAW)

    result = resume_progress(_doc(RunOutcome.FAILED, SAW), origin, 1, False)

    assert result is ResumeFailure.EXITED_BEFORE_CLAIM


def test_an_unknown_origin_never_confirms_a_failed_run() -> None:
    result = resume_progress(_doc(RunOutcome.FAILED, LATER), None, None, False)

    assert result == STILL_RESUMING


def _entry(result: dict[str, object] | None) -> JournalEntry:
    return JournalEntry("e", "p", "n", CommandKind.SQ_RUN, result=result)


def test_the_state_is_read_from_the_recorded_document() -> None:
    document = _doc(RunOutcome.ORPHANED, SAW).model_dump(mode="json")

    origin = resumed_from_entry(_entry({"outcome_document": document}))

    assert origin == ResumedFrom(RunOutcome.ORPHANED, SAW, None)


def test_no_entry_or_document_is_an_unknown_origin() -> None:
    assert resumed_from_entry(None) is None
    assert resumed_from_entry(_entry(None)) is None
