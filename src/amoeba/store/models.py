"""What the program tables hold, as frozen values (slice 222, D3).

JSON array columns are decoded into tuples; timestamps are timezone-aware UTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from amoeba.answering.values import (
    AnsweredBy,
    AnsweringEvidence,
    DeclineReason,
    PassageRef,
)
from amoeba.store.vocabulary import ConsumedMode, QuestionState, ResumeOutcome


@dataclass(frozen=True)
class Program:
    """A named group of members. The two concept columns are both null or both set."""

    program_id: str
    #: Context Forge project id of the member that holds the concept document.
    concept_member: str | None
    #: Repo-relative path of the concept document in that member.
    concept_path: str | None
    registered_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MemberSettings:
    """What a member's answering depends on; the member's own part of the row."""

    #: Context Forge project id, the member's key.
    project_id: str
    rules_paths: tuple[str, ...]
    #: Config item keys taken off this member's not-authorized list.
    authorize_allow: tuple[str, ...]
    #: Config item keys put on it.
    authorize_deny: tuple[str, ...]


@dataclass(frozen=True)
class Member:
    """A repo in a program."""

    program_id: str
    settings: MemberSettings
    registered_at: datetime
    updated_at: datetime

    @property
    def project_id(self) -> str:
        return self.settings.project_id


@dataclass(frozen=True)
class DependencyPair:
    """``consumer_id`` depends on ``provider_id``; both are members of one program."""

    program_id: str
    provider_id: str
    consumer_id: str
    consumed: ConsumedMode
    registered_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class QuestionKey:
    """A question's identity: the run and the checkpoint time exactly as Squadron
    printed it (slice 223, D1)."""

    run_id: str
    paused_at: str


@dataclass(frozen=True)
class QuestionRecord:
    """One row of ``questions``."""

    key: QuestionKey
    member_id: str
    question: str
    checkout: str
    state: QuestionState
    answering_run_id: str | None
    waiting_reason: DeclineReason | None
    waiting_detail: str | None
    slice_label: str | None
    source_commit: str | None
    passages: tuple[PassageRef, ...] | None
    evidence: AnsweringEvidence | None
    claimed_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AnswerRecord:
    """One row of ``answers``."""

    seq: int
    key: QuestionKey
    answered_by: AnsweredBy
    answer: str
    cited: tuple[str, ...] | None
    recorded_at: datetime
    resume_outcome: ResumeOutcome | None
    resume_detail: str | None
    resume_log: str | None
    resume_at: datetime | None


@dataclass(frozen=True)
class PmPrecedent:
    """The newest PM answer to one of a member's questions."""

    key: QuestionKey
    question: str
    slice_label: str | None
    answer_seq: int
    answer: str
    recorded_at: datetime
