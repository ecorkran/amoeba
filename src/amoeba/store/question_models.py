"""The question record's vocabularies, transition table and models (slice 141).

Every agent question becomes one ``question_records`` row. The vocabularies are
closed: a stored value outside them raises ``UnknownVocabularyValueError`` in the
row mapper, never a defaulted record. ``QUESTION_TRANSITIONS`` is the one
statement of the legal state changes; every writer checks it under the write
lock.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from amoeba.store.journal_models import JournalEntry


class QuestionState(StrEnum):
    """Where a question stands."""

    PENDING = "pending"
    ANSWERING = "answering"
    ANSWERED = "answered"
    DECLINED = "declined"


class AnsweredBy(StrEnum):
    """Who answered a question."""

    ANSWERER = "answerer"
    PM = "pm"


#: The decision every answerer resolution carries. The store spells the string
#: itself because no store module imports the Runner, where ``ResolutionDecision``
#: lives; a test pins the two together (slice 142, D5).
ANSWER_DECISION: Final = "resume"


class DeclineReason(StrEnum):
    """Why a question was not answered by the answerer."""

    NODE_ALREADY_BLOCKED = "node_already_blocked"
    QUESTION_MISSING = "question_missing"
    ANSWERER_NOT_CONFIGURED = "answerer_not_configured"
    NO_ANSWER_ON_FILE = "no_answer_on_file"
    ANSWER_LIMIT_REACHED = "answer_limit_reached"
    RESERVED_TERM = "reserved_term"
    # Slice 144, D8. ``NO_ANSWER_ON_FILE`` stays above: records written before
    # 144 hold it.
    SOURCES_TOO_LARGE = "sources_too_large"
    SOURCES_MISSING = "sources_missing"
    SOURCES_UNREADABLE = "sources_unreadable"
    ANSWERING_LAUNCH_FAILED = "answering_launch_failed"
    ANSWERING_RUN_FAILED = "answering_run_failed"
    ANSWERING_RUN_STALLED = "answering_run_stalled"
    ANSWERING_COST_CAP = "answering_cost_cap"
    ANSWERING_RUN_ORPHANED = "answering_run_orphaned"
    ANSWER_DISCARDED = "answer_discarded"
    ARTIFACT_MISSING = "artifact_missing"
    ARTIFACT_MALFORMED = "artifact_malformed"
    ANSWERER_DECLINED = "answerer_declined"
    UNCITED = "uncited"
    UNKNOWN_CITATION = "unknown_citation"
    CHECK_SAID_NO = "check_said_no"


#: Legal state changes. ``answered`` is terminal. ``declined`` reaches only
#: ``answered``: the PM can still answer a question the answerer declined.
QUESTION_TRANSITIONS: Final[Mapping[QuestionState, frozenset[QuestionState]]] = {
    QuestionState.PENDING: frozenset(
        {QuestionState.ANSWERING, QuestionState.ANSWERED, QuestionState.DECLINED}
    ),
    QuestionState.ANSWERING: frozenset(
        {QuestionState.ANSWERED, QuestionState.DECLINED}
    ),
    QuestionState.DECLINED: frozenset({QuestionState.ANSWERED}),
    QuestionState.ANSWERED: frozenset(),
}


@dataclass(frozen=True)
class QuestionCatch:
    """What ingest knows about a question when it writes the record."""

    project_id: str
    node_id: str
    source_entry_id: str
    run_id: str
    step: str | None
    question: str | None
    truncated: bool


@dataclass(frozen=True)
class QuestionRecord:
    """One stored question, with what became of it."""

    id: str
    project_id: str
    node_id: str
    source_entry_id: str
    run_id: str
    step: str | None
    question: str | None
    truncated: bool
    blocked_state_id: str | None
    state: QuestionState
    answered_by: AnsweredBy | None
    answer: str | None
    decline_reason: DeclineReason | None
    created_at: datetime
    updated_at: datetime
    #: The configured term the gate declined on; set only for ``RESERVED_TERM``.
    reserved_term: str | None
    #: What an answering run rested on (slice 144, D11). All ``None`` on a record
    #: written before migration 015, and until the field's writer has run.
    answering_entry_id: str | None
    source_commit: str | None
    passage_index: tuple[PassageRef, ...] | None
    dropped_pm_answers: tuple[str, ...] | None
    proposed_answer: str | None
    cited_passages: tuple[str, ...] | None
    check_verdict: str | None
    check_reason: str | None
    decline_detail: str | None


@dataclass(frozen=True)
class PassageRef:
    """Where one passage offered to the answerer came from; never its text."""

    id: str
    #: A path at the source commit, or a PM answer's record id.
    source: str
    #: Set only for a PM passage: the question record it was answered on.
    question_id: str | None
    date: datetime


@dataclass(frozen=True)
class AnsweringLaunch:
    """What ``begin_answering`` journals and records at launch (D5)."""

    node_id: str
    run_id: str
    #: The ``sq_answer`` entry's parameters; must carry the kind's required keys.
    parameters: Mapping[str, object]
    source_commit: str
    passages: tuple[PassageRef, ...]
    dropped_pm_answers: tuple[str, ...]


@dataclass(frozen=True)
class AnsweringEvidence:
    """What the answer and check steps produced, as far as the run got (D9)."""

    proposed_answer: str | None = None
    cited: tuple[str, ...] | None = None
    verdict: str | None = None
    reason: str | None = None


class BeginStatus(StrEnum):
    """What ``begin_answering`` did."""

    BEGUN = "begun"
    BLOCK_RESOLVED = "block_resolved"
    SETTLED = "settled"


@dataclass(frozen=True)
class BeginOutcome:
    """The result of one ``begin_answering``. ``entry`` and ``record`` are set only
    when ``status`` is ``BEGUN``; the other outcomes write nothing."""

    status: BeginStatus
    entry: JournalEntry | None
    record: QuestionRecord | None


@dataclass(frozen=True)
class GateRefusal:
    """Why the answer gate refused an answer."""

    reason: DeclineReason
    #: The term as configured; set only when ``reason`` is ``RESERVED_TERM``.
    reserved_term: str | None


#: The gate ``submit_answer`` calls under its write lock: the question text and
#: the count of answers the answerer already gave this run. ``None`` passes.
type AnswerGate = Callable[[str, int], GateRefusal | None]


class AnswerOutcome(StrEnum):
    """What ``submit_answer`` did."""

    SUBMITTED = "submitted"
    DECLINED = "declined"
    BLOCK_RESOLVED = "block_resolved"
    SETTLED = "settled"


@dataclass(frozen=True)
class AnswerSubmission:
    """The outcome of one ``submit_answer`` and the record as it then stands."""

    outcome: AnswerOutcome
    record: QuestionRecord
