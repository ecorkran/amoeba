"""The result values of the pause operations (slice 223, D3, D8, D13)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from amoeba.answering.values import DeclineReason
from amoeba.store.models import QuestionKey
from amoeba.store.vocabulary import ResumeOutcome


@dataclass(frozen=True)
class ResumeResult:
    """What handing an answer back to the paused run came to (D8)."""

    outcome: ResumeOutcome
    #: Why it was refused or not delivered; ``None`` for a resume that took.
    detail: str | None
    #: Path of the resume's stdout log, when a child was started.
    resume_log: str | None


class SkipReason(StrEnum):
    """Why ``handle_pause`` left a pause alone (the D3 table, in its order)."""

    NOT_PAUSED = "not_paused"
    NOT_AGENT_QUESTION = "not_agent_question"
    NO_QUESTION_TEXT = "no_question_text"
    ANSWERING_RUN = "answering_run"
    NOT_A_PROJECT = "not_a_project"
    NOT_IN_PROGRAM = "not_in_program"
    PROMPT_ONLY = "prompt_only"
    OTHER_MEMBER = "other_member"
    ALREADY_CLAIMED = "already_claimed"
    WAITING_ON_PM = "waiting_on_pm"
    SETTLED = "settled"
    CLOSED = "closed"
    WRONG_CHECKOUT = "wrong_checkout"


class HandlePauseOutcome(StrEnum):
    """How a ``handle_pause`` call ended."""

    SKIPPED = "skipped"
    WAITING_ON_PM = "waiting_on_pm"
    SUPERSEDED = "superseded"
    RESUMED = "resumed"
    REFUSED = "refused"
    NOT_DELIVERED = "not_delivered"


@dataclass(frozen=True)
class HandlePauseResult:
    """The result of ``handle_pause``. Fields that do not apply are ``None``."""

    outcome: HandlePauseOutcome
    #: Set when ``outcome`` is ``skipped``.
    skip_reason: SkipReason | None = None
    #: Set when ``outcome`` is ``waiting_on_pm``.
    waiting_reason: DeclineReason | None = None
    detail: str | None = None
    #: The question this call concerned, once it got that far.
    key: QuestionKey | None = None
    #: The checkout the question was claimed in.
    checkout: str | None = None
    answering_run_id: str | None = None
    answer_seq: int | None = None
