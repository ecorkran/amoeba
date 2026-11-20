"""The passage and its kind, apart from ``passages`` so the request passage module
can build one without importing the assembly that places it (slice 242)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class PassageKind(StrEnum):
    """The ``kind:`` words of 140's ``passages.md`` format."""

    RULE = "rule"
    PLAN = "plan"
    PM_ANSWER = "pm_answer"
    PROGRAM_CONCEPT = "program_concept"
    PROGRAM_MEMBERS = "program_members"
    #: The reply another project gave to a request this one sent (242 D5).
    REQUEST_RESULT = "request_result"
    #: A ruling the PM gave ahead of time, for every case it describes (230 D5).
    STANDING_ANSWER = "standing_answer"


@dataclass(frozen=True)
class Passage:
    """One numbered, dated piece of source text."""

    id: str
    kind: PassageKind
    #: Repo-relative path for a rule, plan or concept passage; the program id for the
    #: member list (recorded, not rendered); the request id for a request result;
    #: ``None`` for a PM answer.
    source: str | None
    date: datetime
    text: str
    #: PM answers only: the question the PM answered.
    question: str | None
    #: PM answers only: the slice the question was about.
    slice_label: str | None
    #: PM answers only: the record it came from. Not rendered.
    question_id: str | None
    #: Program concept: the project that holds the concept file. Request result:
    #: the project that replied.
    member: str | None
