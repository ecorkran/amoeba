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
    optional_timestamp,
    text,
    vocabulary,
)
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import Door, QuestionState, ResumeOutcome


def answer_from_row(row: Sequence[object]) -> AnswerRecord:
    """An ``AnswerRecord`` from a row of ``sql.ANSWER_COLUMNS``."""
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
        resume_at=optional_timestamp(row[10], "answers.resume_at"),
        retracted_at=optional_timestamp(row[11], "answers.retracted_at"),
        retract_reason=optional_text(row[12], "answers.retract_reason"),
        resume_started_at=optional_timestamp(row[13], "answers.resume_started_at"),
        via=None if row[14] is None else vocabulary(row[14], Door, "answers.via"),
    )


# --- reads ------------------------------------------------------------------


def answers_of(transaction: Transaction, key: QuestionKey) -> tuple[AnswerRecord, ...]:
    """Every answer to the question, in ``seq`` order."""
    rows = transaction.execute(
        sql.SELECT_ANSWERS_OF, (key.run_id, key.paused_at)
    ).fetchall()
    return tuple(answer_from_row(row) for row in rows)


def get_answer(transaction: Transaction, seq: int) -> AnswerRecord | None:
    """The answer row with this ``seq``."""
    row = transaction.execute(sql.SELECT_ANSWER, (seq,)).fetchone()
    return None if row is None else answer_from_row(row)


def latest_answer(transaction: Transaction, key: QuestionKey) -> AnswerRecord | None:
    """The answer with the highest ``seq``: the one a resume delivers."""
    row = transaction.execute(
        sql.SELECT_LATEST_ANSWER, (key.run_id, key.paused_at)
    ).fetchone()
    return None if row is None else answer_from_row(row)


def automatic_answer_count(transaction: Transaction, run_id: str) -> int:
    """Answers the answerer gave this run, across every ``paused_at``, since the
    run's newest PM answer (all of them if it has none). PM answers never count
    toward the limit, and one resets it, retracted or not (228 D7)."""
    row = transaction.execute(
        sql.COUNT_AUTOMATIC_ANSWERS,
        (run_id, AnsweredBy.ANSWERER.value, run_id, AnsweredBy.PM.value),
    ).fetchone()
    return 0 if row is None else integer(row[0], "count")


def pm_precedent(transaction: Transaction, member_id: str) -> tuple[PmPrecedent, ...]:
    """The newest PM answer to each of the member's questions, oldest first.
    Automatic answers are never precedent. A question gives none when that newest
    answer is retracted or the question is closed; an older PM answer is not brought
    back (228 D6)."""
    pm = AnsweredBy.PM.value
    rows = transaction.execute(
        sql.SELECT_PM_PRECEDENT, (member_id, pm, pm, QuestionState.CLOSED.value)
    ).fetchall()
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
    transaction: Transaction,
    key: QuestionKey,
    answer: str,
    *,
    now: datetime,
    via: Door | None,
) -> int:
    """Add a PM answer and set the question ``answered`` from any state; returns the
    answer's ``seq``. ``waiting_reason`` and ``waiting_detail`` stay as they were.

    ``via`` is the door that carried the answer. It is required so no writer records
    a PM answer without saying where it came from; ``None`` is for a caller that
    builds a row as it was before migration 004 (a test fixture)."""
    recorded = encode_timestamp(now)
    cursor = transaction.execute(
        sql.INSERT_RECORDED_ANSWER,
        (
            key.run_id,
            key.paused_at,
            AnsweredBy.PM.value,
            answer,
            None,
            recorded,
            None if via is None else via.value,
        ),
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


def retract_answer(
    transaction: Transaction, seq: int, reason: str, *, now: datetime
) -> bool:
    """Mark the answer retracted, once. True if this call set it, False if it was
    already retracted or does not exist. The answer stays delivered (228 D6)."""
    cursor = transaction.execute(
        sql.RETRACT_ANSWER, (encode_timestamp(now), reason, seq)
    )
    return cursor.rowcount == 1


def mark_resume_started(
    transaction: Transaction, answer_seq: int, *, now: datetime
) -> bool:
    """Record that a resume is about to be spawned. False when the answer's outcome
    is already final (``resumed`` or ``not_delivered``): nothing may be spawned."""
    cursor = transaction.execute(
        sql.MARK_RESUME_STARTED,
        (encode_timestamp(now), answer_seq, ResumeOutcome.REFUSED.value),
    )
    return cursor.rowcount == 1


def mark_not_delivered(
    transaction: Transaction, answer_seq: int, detail: str, *, now: datetime
) -> bool:
    """Make the answer ``not_delivered`` unless its outcome is final; never
    overwrites ``resumed``. True if it wrote."""
    cursor = transaction.execute(
        sql.MARK_NOT_DELIVERED,
        (
            ResumeOutcome.NOT_DELIVERED.value,
            detail,
            encode_timestamp(now),
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
                None,  # automatic answers are carried by no door
            ),
        )
        return Settled(integer(cursor.lastrowid, "answers.seq"))
