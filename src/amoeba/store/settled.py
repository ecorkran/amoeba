"""Questions that ended recently, for ``list --all`` (slice 229, D3).

A question has settled when it was answered and the answer was handed over (or can no
longer be), or when it was closed. The window is the caller's: ``since`` is the UTC
time the question settled at or after. An open question is never here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from amoeba.answering.values import AnsweredBy
from amoeba.store import sql
from amoeba.store.errors import StoreRowError
from amoeba.store.models import QuestionKey
from amoeba.store.row_values import decode_timestamp, encode_timestamp, text
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import ClosedReason, QuestionState, ResumeOutcome


@dataclass(frozen=True)
class SettledQuestion:
    program_id: str
    member_id: str
    key: QuestionKey
    question: str
    #: Who answered it, or why it was closed.
    ended: AnsweredBy | ClosedReason
    #: When the answer was recorded, or the question was closed.
    settled_at: datetime


def settled_since(
    transaction: Transaction, since: datetime
) -> tuple[SettledQuestion, ...]:
    """Questions settled at or after ``since``, newest first."""
    rows = transaction.execute(
        sql.SELECT_SETTLED_SINCE,
        (
            QuestionState.CLOSED.value,
            encode_timestamp(since),
            QuestionState.ANSWERED.value,
            encode_timestamp(since),
            ResumeOutcome.RESUMED.value,
            ResumeOutcome.NOT_DELIVERED.value,
        ),
    ).fetchall()
    return tuple(_settled(row) for row in rows)


def _ended(value: object) -> AnsweredBy | ClosedReason:
    """The ``ended`` column holds a closed reason or an ``answered_by``. The two
    vocabularies share no value, so trying each in turn tells which it is."""
    word = text(value, "questions.closed_reason / answers.answered_by")
    for vocabulary in (ClosedReason, AnsweredBy):
        try:
            return vocabulary(word)
        except ValueError:
            continue  # not this vocabulary; the other is tried, then it is corrupt
    raise StoreRowError(f"settled row ends with {word!r}, which is neither vocabulary")


def _settled(row: tuple[object, ...]) -> SettledQuestion:
    return SettledQuestion(
        program_id=text(row[0], "members.program_id"),
        member_id=text(row[1], "questions.member_id"),
        key=QuestionKey(
            text(row[2], "questions.run_id"), text(row[3], "questions.paused_at")
        ),
        question=text(row[4], "questions.question"),
        ended=_ended(row[5]),
        settled_at=decode_timestamp(row[6], "settled_at"),
    )
