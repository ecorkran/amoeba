"""``resume_progress``: every row of D6's confirmation and failure table."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from amoeba.process import RunCheckpoint, RunOutcome, RunOutcomeDocument
from amoeba.runner.faults import ResumeFailure
from amoeba.runner.resolutions.confirm import (
    CONFIRMED,
    STILL_RESUMING,
    resume_progress,
)

OLD = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)
NEW = OLD + timedelta(hours=1)


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
        resume_progress(_poll(RunOutcome.PAUSED, OLD), OLD, None, False)
        == STILL_RESUMING
    )


def test_a_missing_run_is_run_missing() -> None:
    result = resume_progress(_poll(RunOutcome.NOT_FOUND), OLD, None, False)

    assert result is ResumeFailure.RUN_MISSING


def test_exit_two_at_the_old_pause_is_refused() -> None:
    result = resume_progress(_poll(RunOutcome.PAUSED, OLD), OLD, 2, False)

    assert result is ResumeFailure.REFUSED


@pytest.mark.parametrize("code", [0, 1, 3, 137])
def test_another_exit_code_at_the_old_pause_exited_before_claim(code: int) -> None:
    result = resume_progress(_poll(RunOutcome.PAUSED, OLD), OLD, code, False)

    assert result is ResumeFailure.EXITED_BEFORE_CLAIM


@pytest.mark.parametrize("exit_code", [None])
def test_no_claim_within_grace_with_a_running_or_untracked_child(
    exit_code: int | None,
) -> None:
    result = resume_progress(_poll(RunOutcome.PAUSED, OLD), OLD, exit_code, True)

    assert result is ResumeFailure.NO_CLAIM_WITHIN_GRACE


def test_an_unknown_resumed_from_never_confirms_a_pause() -> None:
    inside = resume_progress(_poll(RunOutcome.PAUSED, NEW), None, None, False)
    past = resume_progress(_poll(RunOutcome.PAUSED, NEW), None, None, True)

    assert inside == STILL_RESUMING
    assert past is ResumeFailure.NO_CLAIM_WITHIN_GRACE


def test_a_pause_with_no_paused_at_cannot_be_judged_new() -> None:
    result = resume_progress(_poll(RunOutcome.PAUSED), OLD, None, True)

    assert result is ResumeFailure.NO_CLAIM_WITHIN_GRACE
