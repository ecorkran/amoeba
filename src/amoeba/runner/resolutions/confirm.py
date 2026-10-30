"""When is a resume confirmed, still going, or failed (slice 127, D6; slice 132, D5).

Pure: the observer hands over one poll, the state the resume started from, the
tracked child's exit code and whether the launch grace period has passed. Failure is
decided on observed state and exit code, never on message text.

A resume is confirmed when the run leaves the state it was resumed from: that state is
the resumed-from entry's recorded outcome and ``updated_at`` (and, for a pause, its
``paused_at``). It holds for every resume, automatic or by resolution, and for a run
resumed from ``paused``, ``failed`` or ``orphaned``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from amoeba.process import SQ_USAGE_ERROR_EXIT_CODE, RunOutcome, RunOutcomeDocument
from amoeba.runner.faults import ResumeFailure
from amoeba.runner.supervise import recorded_document
from amoeba.store import JournalEntry

#: The outcomes of a run that stopped but can be resumed: the states a resume leaves.
STOPPED_OUTCOMES: Final = frozenset(
    {RunOutcome.PAUSED, RunOutcome.FAILED, RunOutcome.ORPHANED}
)


@dataclass(frozen=True)
class Confirmed:
    """The run has left the state it was resumed from."""


@dataclass(frozen=True)
class StillResuming:
    """The poll still shows the old state and nothing has failed yet."""


#: One value each: they carry no data.
CONFIRMED: Final = Confirmed()
STILL_RESUMING: Final = StillResuming()


@dataclass(frozen=True)
class ResumedFrom:
    """The state a resume was issued from, as the resumed-from entry recorded it."""

    outcome: RunOutcome
    updated_at: datetime | None = None
    paused_at: datetime | None = None


def resumed_from_entry(entry: JournalEntry | None) -> ResumedFrom | None:
    """The state ``entry``'s recorded outcome document shows, or ``None`` if unknown."""
    document = None if entry is None else recorded_document(entry)
    if document is None:
        return None
    paused_at = None if document.checkpoint is None else document.checkpoint.paused_at
    return ResumedFrom(document.outcome, document.updated_at, paused_at)


def has_left(poll: RunOutcomeDocument, origin: ResumedFrom) -> bool:
    """Whether the polled run is no longer in the state ``origin`` describes."""
    if poll.outcome is not origin.outcome:
        return True
    if (
        poll.updated_at is not None
        and origin.updated_at is not None
        and poll.updated_at > origin.updated_at
    ):
        return True
    paused_at = None if poll.checkpoint is None else poll.checkpoint.paused_at
    return (
        origin.paused_at is not None
        and paused_at is not None
        and paused_at != origin.paused_at
    )


def is_at(poll: RunOutcomeDocument, origin: ResumedFrom) -> bool:
    """Whether the polled run is positively still in the state ``origin`` describes.

    A pause also has to show the same ``paused_at``: a pause that cannot be told
    apart from the old one is not trusted to be it.
    """
    if has_left(poll, origin):
        return False
    paused_at = None if poll.checkpoint is None else poll.checkpoint.paused_at
    return origin.paused_at is None or paused_at == origin.paused_at


def resume_progress(
    poll: RunOutcomeDocument,
    resumed_from: ResumedFrom | None,
    exit_code: int | None,
    past_grace: bool,
) -> Confirmed | StillResuming | ResumeFailure:
    """Judge one poll of a resume that is not yet confirmed.

    Args:
        poll: The latest poll of the run.
        resumed_from: The state the resume was issued from, or ``None`` if it could
            not be read, in which case a stopped run is never confirmed.
        exit_code: The tracked child's exit code, ``None`` while it runs or when no
            child is tracked (after a restart).
        past_grace: Whether ``launch_grace_seconds`` have passed since ``issued_at``.
    """
    if poll.outcome is RunOutcome.NOT_FOUND:
        return ResumeFailure.RUN_MISSING
    if poll.outcome not in STOPPED_OUTCOMES:
        return CONFIRMED
    if resumed_from is not None and has_left(poll, resumed_from):
        return CONFIRMED
    if exit_code == SQ_USAGE_ERROR_EXIT_CODE:
        return ResumeFailure.REFUSED
    if exit_code is not None:
        return ResumeFailure.EXITED_BEFORE_CLAIM
    return ResumeFailure.NO_CLAIM_WITHIN_GRACE if past_grace else STILL_RESUMING
