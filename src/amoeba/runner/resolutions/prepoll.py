"""What a continuation does once its pre-poll has answered (slice 127, D4 step 1).

Pure: the caller polls the run once and hands over the answer. Nothing is written
before this has decided, so a routine cut-off never leaves an entry with no launch
behind it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from amoeba.process import PollFailure, RunOutcome, RunPoll
from amoeba.runner.decide import ObserveRun, ResumeRun
from amoeba.runner.resolutions.confirm import STOPPED_OUTCOMES, ResumedFrom, is_at
from amoeba.runner.resolutions.vocabulary import RESUME_SKIPPED_RUN_NOT_AT_PAUSE


class Act(StrEnum):
    """What Act does next for a continuation."""

    #: Write nothing; the step stays as it is for the next tick.
    WAIT = "wait"
    #: The run is gone: record a failed resume, launch nothing.
    RUN_MISSING = "run_missing"
    #: Journal an observation entry and launch nothing.
    OBSERVE = "observe"
    #: Journal the entry and launch ``sq run --resume``.
    LAUNCH = "launch"


@dataclass(frozen=True)
class PrepollDecision:
    """The act, and why when it matters.

    ``detail`` is the poll failure text for ``WAIT``. ``resume_skipped`` is set for
    an ``OBSERVE`` that stands in for a resume the run had moved past.
    """

    act: Act
    detail: str | None = None
    resume_skipped: str | None = None


def prepoll_decision(
    action: ResumeRun | ObserveRun, poll: RunPoll, resumed_from: ResumedFrom | None
) -> PrepollDecision:
    """Decide the act from the one pre-poll.

    ``resumed_from`` is the state the continued entry recorded. A resume is carried
    out only on the state it was decided for, whether a pause or a transient failure:
    a run that has left it, for example because the PM resumed it by hand or its
    owner came back, is observed instead.
    """
    if isinstance(poll, PollFailure):
        return PrepollDecision(Act.WAIT, detail=poll.reason)
    if poll.outcome is RunOutcome.NOT_FOUND:
        return PrepollDecision(Act.RUN_MISSING)
    if isinstance(action, ObserveRun):
        return PrepollDecision(Act.OBSERVE)
    if (
        poll.outcome in STOPPED_OUTCOMES
        and resumed_from is not None
        and is_at(poll, resumed_from)
    ):
        return PrepollDecision(Act.LAUNCH)
    return PrepollDecision(Act.OBSERVE, resume_skipped=RESUME_SKIPPED_RUN_NOT_AT_PAUSE)
