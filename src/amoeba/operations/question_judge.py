"""The close sweep's judging, on a transaction (slice 228, D4; split out in 262).

A leaf apart from ``question_sweep`` so the hub's ``pause_begin`` and the hub part of
``status`` run the same table without reaching the code that polls ``sq``. Every move
is a compare-and-set on the row's state and ``updated_at``, so a concurrent ``answer``,
``dismiss`` or settle wins and the sweep skips that row.

An answer with no outcome is left (262 D9): its resume attempt records the outcome. A
``refused`` one becomes ``not_delivered`` once its newest sign of life is
``resume_claim_seconds`` old.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from amoeba.config.user_config import UserConfig
from amoeba.operations.steps.limits import pause_claim_seconds, resume_claim_seconds
from amoeba.store.answers import latest_answer, mark_not_delivered
from amoeba.store.models import AnswerRecord, QuestionKey, QuestionRecord
from amoeba.store.question_closing import close_question
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import ClosedReason, QuestionState, ResumeOutcome


@dataclass(frozen=True)
class RunFate:
    """Where a run is now, as far as it matters to its older open questions."""

    #: ``RUN_MOVED_ON`` or ``RUN_GONE``.
    reason: ClosedReason
    #: The run's state, or the later pause, recorded as ``closed_detail``.
    detail: str
    #: The pause the run is at now; a row there is never touched. ``None`` when the
    #: run is not paused.
    current_paused_at: str | None


@dataclass(frozen=True)
class ClosedQuestion:
    """A question this sweep closed."""

    key: QuestionKey
    member_id: str
    question: str
    closed_reason: ClosedReason
    closed_detail: str


@dataclass(frozen=True)
class UndeliveredAnswer:
    """An answer this sweep marked ``not_delivered``."""

    key: QuestionKey
    member_id: str
    question: str
    answer_seq: int
    resume_outcome: ResumeOutcome
    detail: str


@dataclass(frozen=True)
class SweepResult:
    """What a sweep closed, and why it could not if its write lost the lock."""

    closed: tuple[ClosedQuestion, ...] = ()
    undelivered: tuple[UndeliveredAnswer, ...] = ()
    #: Set when the write could not take the lock; nothing was closed.
    problem: str | None = None

    @property
    def changed_anything(self) -> bool:
        return bool(self.closed or self.undelivered)


def judge_in(
    transaction: Transaction,
    config: UserConfig,
    judged: Sequence[tuple[QuestionRecord, RunFate]],
    now: datetime,
) -> SweepResult:
    """Apply the D4 table to each (row, fate) in the caller's write transaction."""
    closed: list[ClosedQuestion] = []
    undelivered: list[UndeliveredAnswer] = []
    for row, fate in judged:
        _judge(transaction, config, row, fate, now, closed, undelivered)
    return SweepResult(tuple(closed), tuple(undelivered))


def _judge(  # noqa: PLR0913 - one row of the D4 table and its outputs
    transaction: Transaction,
    config: UserConfig,
    row: QuestionRecord,
    fate: RunFate,
    now: datetime,
    closed: list[ClosedQuestion],
    undelivered: list[UndeliveredAnswer],
) -> None:
    match row.state:
        # A held question has no claim to wait for, so it closes as a waiting one
        # does (242 D8).
        case QuestionState.WAITING_ON_PM | QuestionState.WAITING_ON_REQUEST:
            _close(transaction, row, fate, now, closed)
        case QuestionState.CLAIMED:
            # A young claim is left alone: its answering run may still settle. Its
            # age is from the last write to it, as every judge of a claim measures it.
            if now - row.updated_at >= timedelta(seconds=pause_claim_seconds(config)):
                _close(transaction, row, fate, now, closed)
        case QuestionState.ANSWERED:
            _mark_undelivered(transaction, config, row, fate, now, undelivered)
        case QuestionState.CLOSED:
            return


def _close(
    transaction: Transaction,
    row: QuestionRecord,
    fate: RunFate,
    now: datetime,
    closed: list[ClosedQuestion],
) -> None:
    if close_question(
        transaction, row.key, fate.reason, fate.detail, row.state, row.updated_at, now
    ):
        closed.append(
            ClosedQuestion(
                row.key, row.member_id, row.question, fate.reason, fate.detail
            )
        )


def _mark_undelivered(  # noqa: PLR0913 - one row of the D4 table and its output
    transaction: Transaction,
    config: UserConfig,
    row: QuestionRecord,
    fate: RunFate,
    now: datetime,
    undelivered: list[UndeliveredAnswer],
) -> None:
    # Read again inside this transaction: a resume or a new answer since the caller's
    # read moves the newest sign of life, and this write is serialized with them.
    latest = latest_answer(transaction, row.key)
    # An answer with no outcome is work for its machine (262 D9, D10): its resume
    # attempt records the outcome, so the sweep leaves it. Only a refused one is
    # judged, from its newest sign of life, at the claim's own bound.
    if latest is None or latest.resume_outcome is not ResumeOutcome.REFUSED:
        return
    if now - _newest_sign(latest) < timedelta(seconds=resume_claim_seconds(config)):
        return
    if mark_not_delivered(transaction, latest.seq, fate.detail, now=now):
        undelivered.append(
            UndeliveredAnswer(
                row.key,
                row.member_id,
                row.question,
                latest.seq,
                ResumeOutcome.NOT_DELIVERED,
                fate.detail,
            )
        )


def _newest_sign(answer: AnswerRecord) -> datetime:
    """The newest of when the answer was recorded, its resume started and its last
    outcome was recorded: the last time anything was in flight for it."""
    return max(
        moment
        for moment in (answer.recorded_at, answer.resume_started_at, answer.resume_at)
        if moment is not None
    )
