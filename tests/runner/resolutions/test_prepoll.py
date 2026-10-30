"""``prepoll_decision``: every branch of D4 step 1."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from amoeba.process import (
    PollFailure,
    RunCheckpoint,
    RunOutcome,
    RunOutcomeDocument,
    RunPoll,
)
from amoeba.runner.decide import ObserveRun, ResumeRun
from amoeba.runner.resolutions.confirm import ResumedFrom
from amoeba.runner.resolutions.prepoll import Act, PrepollDecision, prepoll_decision
from amoeba.runner.resolutions.vocabulary import (
    RESUME_SKIPPED_RUN_NOT_AT_PAUSE,
    Continuation,
    ResumeCause,
)

PAUSED_AT = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)
PAUSED = ResumedFrom(RunOutcome.PAUSED, paused_at=PAUSED_AT)
CHECKOUT = Path("/work/a")
RESUME = ResumeRun(
    "n", "r", Continuation.RETRY, "e", "b", CHECKOUT, cause=ResumeCause.RESOLUTION
)
OBSERVE = ObserveRun("n", "r", "e", "b", CHECKOUT)


def _poll(outcome: RunOutcome, paused_at: datetime | None = None) -> RunPoll:
    checkpoint = None if paused_at is None else RunCheckpoint(paused_at=paused_at)
    return RunOutcomeDocument(run_id="r", outcome=outcome, checkpoint=checkpoint)


def test_a_failed_poll_waits_and_says_why() -> None:
    decision = prepoll_decision(RESUME, PollFailure("sq timed out"), PAUSED)

    assert decision == PrepollDecision(Act.WAIT, detail="sq timed out")


@pytest.mark.parametrize("action", [RESUME, OBSERVE])
def test_no_run_state_is_run_missing(action: ResumeRun | ObserveRun) -> None:
    decision = prepoll_decision(action, _poll(RunOutcome.NOT_FOUND), PAUSED)

    assert decision.act is Act.RUN_MISSING


def test_a_run_still_at_its_pause_is_launched() -> None:
    decision = prepoll_decision(RESUME, _poll(RunOutcome.PAUSED, PAUSED_AT), PAUSED)

    assert decision == PrepollDecision(Act.LAUNCH)


@pytest.mark.parametrize(
    "poll",
    [
        _poll(RunOutcome.PAUSED, PAUSED_AT + timedelta(minutes=5)),
        _poll(RunOutcome.PAUSED),
        _poll(RunOutcome.COMPLETED),
        _poll(RunOutcome.TIMED_OUT),
        _poll(RunOutcome.FAILED),
        _poll(RunOutcome.UNREADABLE),
    ],
)
def test_a_run_that_left_its_pause_is_observed_with_the_reason(poll: RunPoll) -> None:
    decision = prepoll_decision(RESUME, poll, PAUSED)

    assert decision == PrepollDecision(
        Act.OBSERVE, resume_skipped=RESUME_SKIPPED_RUN_NOT_AT_PAUSE
    )


def test_a_resume_with_no_recorded_pause_cannot_be_matched() -> None:
    decision = prepoll_decision(RESUME, _poll(RunOutcome.PAUSED, PAUSED_AT), None)

    assert decision.act is Act.OBSERVE and decision.resume_skipped is not None


@pytest.mark.parametrize(
    "outcome", [RunOutcome.PAUSED, RunOutcome.COMPLETED, RunOutcome.TIMED_OUT]
)
def test_observe_with_a_run_state_observes_without_a_skip_reason(
    outcome: RunOutcome,
) -> None:
    decision = prepoll_decision(OBSERVE, _poll(outcome, PAUSED_AT), PAUSED)

    assert decision == PrepollDecision(Act.OBSERVE)


# -- slice 132, D5: an automatic resume from a failed or orphaned run -------------

SAW = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)


def _stopped(outcome: RunOutcome, updated_at: datetime) -> RunPoll:
    return RunOutcomeDocument(run_id="r", outcome=outcome, updated_at=updated_at)


@pytest.mark.parametrize("stopped", [RunOutcome.FAILED, RunOutcome.ORPHANED])
def test_a_run_still_in_its_failed_or_orphaned_state_is_launched(
    stopped: RunOutcome,
) -> None:
    origin = ResumedFrom(stopped, SAW)

    decision = prepoll_decision(RESUME, _stopped(stopped, SAW), origin)

    assert decision == PrepollDecision(Act.LAUNCH)


@pytest.mark.parametrize("stopped", [RunOutcome.FAILED, RunOutcome.ORPHANED])
def test_a_run_that_moved_on_from_its_failure_is_observed_not_resumed(
    stopped: RunOutcome,
) -> None:
    origin = ResumedFrom(stopped, SAW)
    later = SAW + timedelta(minutes=1)

    assert prepoll_decision(RESUME, _stopped(stopped, later), origin) == (
        PrepollDecision(Act.OBSERVE, resume_skipped=RESUME_SKIPPED_RUN_NOT_AT_PAUSE)
    )
    running = RunOutcomeDocument(run_id="r", outcome=RunOutcome.TIMED_OUT)
    assert prepoll_decision(RESUME, running, origin).act is Act.OBSERVE
