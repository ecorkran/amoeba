"""The values ``decisions`` returns (slice 224, D5): one record per recorded answer.

Pydantic models, so the CLI prints them with ``model_dump_json``. ``decisions``
re-exports the public ones, so the design's import path holds.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from amoeba.answering.values import AnsweredBy, DeclineReason
from amoeba.operations.reject_codes import RejectCode
from amoeba.store.vocabulary import ResumeOutcome


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MemberName(_Model):
    """A member as shown: its Context Forge project id and name."""

    id: str
    name: str


class CitedPassage(_Model):
    """A passage an automatic answer cited, as recorded when it was offered."""

    id: str
    #: ``pm_answer`` for a PM answer used as precedent. The store records no kind for
    #: other passages, so it is null for them rather than guessed.
    kind: str | None
    source: str
    date: datetime


class AnswererBasis(_Model):
    """What an automatic answer rested on: the passages it cited and the check."""

    cited: tuple[CitedPassage, ...]
    check_verdict: str | None
    check_reason: str | None


class PmBasis(_Model):
    """Why the question reached the PM, when it waited first."""

    waiting_reason: DeclineReason
    waiting_detail: str | None


class ResumeRecord(_Model):
    """What came of handing the answer back to the run."""

    outcome: ResumeOutcome | None
    detail: str | None
    at: datetime | None


class DecisionsRecord(_Model):
    """One recorded answer, with who gave it and from what."""

    seq: int
    recorded_at: datetime
    program: str
    member: MemberName
    run_id: str
    paused_at: str
    slice_label: str | None
    question: str
    answered_by: AnsweredBy
    answer: str
    #: The newest earlier answer to the same question; a PM answer after an automatic
    #: one is an override.
    prior_answer_seq: int | None
    #: Null for a PM answer given before the question ever waited.
    based_on: AnswererBasis | PmBasis | None
    resume: ResumeRecord
    #: Set when the PM answer was retracted (228 D6): it stays delivered and listed
    #: but is no longer precedent.
    retracted_at: datetime | None
    retract_reason: str | None


class DecisionsOutcome(StrEnum):
    LISTED = "listed"
    REJECTED = "rejected"


class DecisionsResult(_Model):
    """The result of ``decisions``. Fields that do not apply are null or empty."""

    outcome: DecisionsOutcome
    rejection: RejectCode | None = None
    records: tuple[DecisionsRecord, ...] = ()
    #: The last listed ``seq``, only when the listing started at the marker, was not
    #: narrowed and is not empty: what ``mark_read`` may safely be given.
    read_through: int | None = None
    #: The marker when read; null when the request was rejected.
    marker: int | None = None
    problems: tuple[str, ...] = ()
