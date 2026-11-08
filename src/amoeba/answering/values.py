"""The vocabulary of answering: who answered, why not, what evidence, which passages.

Moved unchanged from the old store. The library owns these because they say what an
answer is; whatever persists a question record imports them from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

#: The only wildcard in a rules entry or a plan file pattern.
GLOB_WILDCARD: Final = "*"


class AnsweredBy(StrEnum):
    """Who answered a question."""

    ANSWERER = "answerer"
    PM = "pm"


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
class AnsweringEvidence:
    """What the answer and check steps produced, as far as the run got (D9)."""

    proposed_answer: str | None = None
    cited: tuple[str, ...] | None = None
    verdict: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class GateRefusal:
    """Why the answer gate refused an answer."""

    reason: DeclineReason
    #: The term as configured; set only when ``reason`` is ``RESERVED_TERM``.
    reserved_term: str | None
