"""When is a resume confirmed, still going, or failed (slice 127, D6).

Pure: the observer hands over one poll, the pause the resume started from, the
tracked child's exit code and whether the launch grace period has passed. Failure is
decided on observed state and exit code, never on message text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from amoeba.process import SQ_USAGE_ERROR_EXIT_CODE, RunOutcome, RunOutcomeDocument
from amoeba.runner.faults import ResumeFailure


@dataclass(frozen=True)
class Confirmed:
    """The run has left the pause it was resumed from."""


@dataclass(frozen=True)
class StillResuming:
    """The poll still shows the old pause and nothing has failed yet."""


#: One value each: they carry no data.
CONFIRMED: Final = Confirmed()
STILL_RESUMING: Final = StillResuming()


def resume_progress(
    poll: RunOutcomeDocument,
    resumed_from: datetime | None,
    exit_code: int | None,
    past_grace: bool,
) -> Confirmed | StillResuming | ResumeFailure:
    """Judge one poll of a resume that is not yet confirmed.

    Args:
        poll: The latest poll of the run.
        resumed_from: The ``paused_at`` the continued entry recorded, or ``None`` if
            it could not be read, in which case a pause is never confirmed.
        exit_code: The tracked child's exit code, ``None`` while it runs or when no
            child is tracked (after a restart).
        past_grace: Whether ``launch_grace_seconds`` have passed since ``issued_at``.
    """
    if poll.outcome is RunOutcome.NOT_FOUND:
        return ResumeFailure.RUN_MISSING
    if poll.outcome is not RunOutcome.PAUSED:
        return CONFIRMED
    paused_at = None if poll.checkpoint is None else poll.checkpoint.paused_at
    if resumed_from is not None and paused_at is not None and paused_at != resumed_from:
        return CONFIRMED
    if exit_code == SQ_USAGE_ERROR_EXIT_CODE:
        return ResumeFailure.REFUSED
    if exit_code is not None:
        return ResumeFailure.EXITED_BEFORE_CLAIM
    return ResumeFailure.NO_CLAIM_WITHIN_GRACE if past_grace else STILL_RESUMING
