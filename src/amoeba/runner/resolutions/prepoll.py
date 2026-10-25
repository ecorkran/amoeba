"""What a continuation does once its pre-poll has answered (slice 127, D4 step 1).

Pure: the caller polls the run once and hands over the answer. Nothing is written
before this has decided, so a routine cut-off never leaves an entry with no launch
behind it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from amoeba.process import PollFailure, RunOutcome, RunPoll
from amoeba.runner.decide import ObserveRun, ResumeRun
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
    action: ResumeRun | ObserveRun, poll: RunPoll, resumed_from: datetime | None
) -> PrepollDecision:
    """Decide the act from the one pre-poll.

    ``resumed_from`` is the ``paused_at`` the continued entry recorded. A resume is
    carried out only on the pause it was decided for: a run that has left it, for
    example because the PM resumed it by hand, is observed instead.
    """
    if isinstance(poll, PollFailure):
        return PrepollDecision(Act.WAIT, detail=poll.reason)
    if poll.outcome is RunOutcome.NOT_FOUND:
        return PrepollDecision(Act.RUN_MISSING)
    if isinstance(action, ObserveRun):
        return PrepollDecision(Act.OBSERVE)
    paused_at = None if poll.checkpoint is None else poll.checkpoint.paused_at
    if (
        poll.outcome is RunOutcome.PAUSED
        and resumed_from is not None
        and paused_at == resumed_from
    ):
        return PrepollDecision(Act.LAUNCH)
    return PrepollDecision(Act.OBSERVE, resume_skipped=RESUME_SKIPPED_RUN_NOT_AT_PAUSE)
