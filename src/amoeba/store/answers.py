"""Answer reads and writes (slice 223, D4, D8, D9). ``store.questions`` re-exports
these names, so the design's ``store.questions`` interface holds.

Every function takes an open transaction, except :func:`settle_answered`, which owns
its one ``BEGIN IMMEDIATE`` transaction because the gate runs inside it. Answer rows
are never changed apart from their resume columns.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from amoeba.answering.values import AnsweredBy, AnsweringEvidence, GateRefusal
from amoeba.store import sql
from amoeba.store.models import AnswerRecord, PmPrecedent, QuestionKey
from amoeba.store.question_json import (
    parse_cited,
    serialize_cited,
    serialize_evidence,
)
from amoeba.store.row_values import (
    decode_timestamp,
    encode_timestamp,
    integer,
    optional_text,
    text,
    vocabulary,
)
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import QuestionState, ResumeOutcome


def _answer(row: Sequence[object]) -> AnswerRecord:
    resume_at = row[10]
    return AnswerRecord(
        seq=integer(row[0], "answers.seq"),
        key=QuestionKey(
            run_id=text(row[1], "answers.run_id"),
            paused_at=text(row[2], "answers.paused_at"),
        ),
        answered_by=vocabulary(row[3], AnsweredBy, "answers.answered_by"),
        answer=text(row[4], "answers.answer"),
        cited=None if row[5] is None else parse_cited(row[5]),
        recorded_at=decode_timestamp(row[6], "answers.recorded_at"),
        resume_outcome=(
            None
            if row[7] is None
            else vocabulary(row[7], ResumeOutcome, "answers.resume_outcome")
        ),
        resume_detail=optional_text(row[8], "answers.resume_detail"),
        resume_log=optional_text(row[9], "answers.resume_log"),
        resume_at=(
            None
            if resume_at is None
            else decode_timestamp(resume_at, "answers.resume_at")
        ),
    )


# --- reads ------------------------------------------------------------------


def answers_of(transaction: Transaction, key: QuestionKey) -> tuple[AnswerRecord, ...]:
    """Every answer to the question, in ``seq`` order."""
    rows = transaction.execute(
        sql.SELECT_ANSWERS_OF, (key.run_id, key.paused_at)
    ).fetchall()
    return tuple(_answer(row) for row in rows)


def latest_answer(transaction: Transaction, key: QuestionKey) -> AnswerRecord | None:
    """The answer with the highest ``seq``: the one a resume delivers."""
    row = transaction.execute(
        sql.SELECT_LATEST_ANSWER, (key.run_id, key.paused_at)
    ).fetchone()
    return None if row is None else _answer(row)


def automatic_answer_count(transaction: Transaction, run_id: str) -> int:
    """Answers the answerer gave this run, across every ``paused_at``; PM answers
    never count toward the limit."""
    row = transaction.execute(
        sql.COUNT_AUTOMATIC_ANSWERS, (run_id, AnsweredBy.ANSWERER.value)
    ).fetchone()
    return 0 if row is None else integer(row[0], "count")


def pm_precedent(transaction: Transaction, member_id: str) -> tuple[PmPrecedent, ...]:
    """The newest PM answer to each of the member's questions, oldest first.
    Automatic answers are never precedent."""
    pm = AnsweredBy.PM.value
    rows = transaction.execute(sql.SELECT_PM_PRECEDENT, (member_id, pm, pm)).fetchall()
    return tuple(
        PmPrecedent(
            key=QuestionKey(
                run_id=text(row[0], "questions.run_id"),
                paused_at=text(row[1], "questions.paused_at"),
            ),
            question=text(row[2], "questions.question"),
            slice_label=optional_text(row[3], "questions.slice_label"),
            answer_seq=integer(row[4], "answers.seq"),
            answer=text(row[5], "answers.answer"),
            recorded_at=decode_timestamp(row[6], "answers.recorded_at"),
        )
        for row in rows
    )


# --- writes -----------------------------------------------------------------


def add_pm_answer(
    transaction: Transaction, key: QuestionKey, answer: str, *, now: datetime
) -> int:
    """Add a PM answer and set the question ``answered`` from any state; returns the
    answer's ``seq``. ``waiting_reason`` and ``waiting_detail`` stay as they were."""
    recorded = encode_timestamp(now)
    cursor = transaction.execute(
        sql.INSERT_RECORDED_ANSWER,
        (key.run_id, key.paused_at, AnsweredBy.PM.value, answer, None, recorded),
    )
    transaction.execute(
        sql.MARK_QUESTION_ANSWERED,
        (QuestionState.ANSWERED.value, recorded, key.run_id, key.paused_at),
    )
    return integer(cursor.lastrowid, "answers.seq")


def record_resume(
    transaction: Transaction,
    answer_seq: int,
    outcome: ResumeOutcome,
    *,
    detail: str | None,
    log: str | None,
    at: datetime,
) -> bool:
    """Record a resume outcome unless one is final: ``resumed`` and
    ``not_delivered`` are never overwritten, ``refused`` is. True if it wrote."""
    cursor = transaction.execute(
        sql.RECORD_RESUME,
        (
            outcome.value,
            detail,
            log,
            encode_timestamp(at),
            answer_seq,
            ResumeOutcome.REFUSED.value,
        ),
    )
    return cursor.rowcount == 1


@dataclass(frozen=True)
class Settled:
    """The claim moved to ``answered`` and the answerer's row was written."""

    answer_seq: int


@dataclass(frozen=True)
class Lost:
    """The claim is no longer this caller's (a PM answer or another settle won)."""


def settle_answered(
    store: Store,
    key: QuestionKey,
    answering_run_id: str,
    *,
    answer: str,
    cited: tuple[str, ...],
    evidence: AnsweringEvidence,
    gate: Callable[[int], GateRefusal | None],
    now: datetime,
) -> Settled | GateRefusal | Lost:
    """Settle ``claimed -> answered`` for the claim ``answering_run_id`` holds.

    One immediate transaction: ``gate`` gets the count of prior automatic answers
    this run, so two settles cannot both pass the limit. A claim that is already
    gone is ``Lost`` before the gate runs; a decline writes nothing.
    """
    moment = encode_timestamp(now)
    with store.write() as transaction:
        prior = automatic_answer_count(transaction, key.run_id)
        refusal = gate(prior)
        held = transaction.execute(
            sql.SELECT_QUESTION_CLAIM, (key.run_id, key.paused_at)
        ).fetchone()
        if held is None or tuple(held) != (
            QuestionState.CLAIMED.value,
            answering_run_id,
        ):
            return Lost()
        if refusal is not None:
            return refusal
        transaction.execute(
            sql.SETTLE_ANSWERED,
            (
                QuestionState.ANSWERED.value,
                serialize_evidence(evidence),
                moment,
                key.run_id,
                key.paused_at,
                QuestionState.CLAIMED.value,
                answering_run_id,
            ),
        )
        cursor = transaction.execute(
            sql.INSERT_RECORDED_ANSWER,
            (
                key.run_id,
                key.paused_at,
                AnsweredBy.ANSWERER.value,
                answer,
                serialize_cited(cited),
                moment,
            ),
        )
        return Settled(integer(cursor.lastrowid, "answers.seq"))
