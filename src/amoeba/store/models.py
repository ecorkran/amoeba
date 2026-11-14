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
from amoeba.store.vocabulary import (
    ClosedReason,
    ConsumedMode,
    Door,
    QuestionState,
    ResumeOutcome,
    RulesFrom,
)


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
    #: Whether the rules are ``rules_paths`` or the config's default (229 D7).
    rules_from: RulesFrom


@dataclass(frozen=True)
class Member:
    """A repo in a program."""

    program_id: str
    settings: MemberSettings
    registered_at: datetime
    updated_at: datetime
    #: When ``set_up`` removed the member; ``None`` for an active one.
    removed_at: datetime | None

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
    #: Set with ``state`` ``closed``; kept as history if ``answer`` reopens it.
    closed_reason: ClosedReason | None
    #: The dismissal reason, or the run's outcome when the sweep closed it.
    closed_detail: str | None
    closed_at: datetime | None


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
    #: Set when a PM answer was retracted; the answer stays delivered (228 D6).
    retracted_at: datetime | None
    retract_reason: str | None
    #: Set just before each resume spawn (228 D4).
    resume_started_at: datetime | None
    #: The door that carried a PM answer (226 D11); ``None`` for an answer written
    #: before migration 004 and for the answerer's automatic answers.
    via: Door | None


@dataclass(frozen=True)
class PmPrecedent:
    """The newest PM answer to one of a member's questions."""

    key: QuestionKey
    question: str
    slice_label: str | None
    answer_seq: int
    answer: str
    recorded_at: datetime
