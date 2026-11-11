"""Reads and the one write behind ``decisions`` and ``mark_read`` (slice 224, D5, D7).

``answers_since`` joins each answer to its question and the member's program, oldest
first. The store takes ``since`` as the UTC text it stores; turning the PM's input
into that text is the operation's job. ``advance_marker`` owns its one ``BEGIN
IMMEDIATE`` transaction so the check against the last answer and the move are atomic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from amoeba.store import sql
from amoeba.store.answers import answer_from_row
from amoeba.store.models import AnswerRecord, QuestionRecord
from amoeba.store.questions import question_from_row
from amoeba.store.row_values import integer, optional_integer, text
from amoeba.store.store import Store, Transaction

_ANSWER_WIDTH = len(sql.ANSWER_COLUMNS.split(","))
_QUESTION_WIDTH = len(sql.QUESTION_COLUMNS.split(","))


@dataclass(frozen=True)
class DecisionRow:
    """One recorded answer with the question, program and override it belongs to."""

    answer: AnswerRecord
    question: QuestionRecord
    program_id: str
    #: The newest earlier answer to the same question, or ``None`` for the first.
    prior_answer_seq: int | None


def read_marker(transaction: Transaction) -> int:
    """The PM's marker: the last answer ``seq`` they have seen."""
    row = transaction.execute(sql.SELECT_MARKER).fetchone()
    if row is None:
        raise ValueError("pm_marker has no row")
    return integer(row[0], "pm_marker.last_seen_seq")


def answers_since(
    transaction: Transaction,
    *,
    after_seq: int | None = None,
    since: str | None = None,
    program: str | None = None,
) -> tuple[DecisionRow, ...]:
    """Answers after ``after_seq`` or recorded at or after ``since`` (UTC text),
    oldest first by ``seq``; ``program`` narrows to that program's members.

    Raises:
        ValueError: Not exactly one of ``after_seq`` and ``since`` was given.
    """
    if (after_seq is None) == (since is None):
        raise ValueError("give exactly one of after_seq and since")
    statement = (
        sql.SELECT_DECISIONS_AFTER_SEQ
        if after_seq is not None
        else sql.SELECT_DECISIONS_SINCE
    )
    parameters: list[object] = [after_seq if after_seq is not None else since]
    if program is not None:
        statement += sql.DECISIONS_PROGRAM_CLAUSE
        parameters.append(program)
    rows = transaction.execute(statement + sql.DECISIONS_ORDER, parameters).fetchall()
    return tuple(_decision(row) for row in rows)


def _decision(row: tuple[object, ...]) -> DecisionRow:
    question_end = _ANSWER_WIDTH + _QUESTION_WIDTH
    return DecisionRow(
        answer=answer_from_row(row[:_ANSWER_WIDTH]),
        question=question_from_row(row[_ANSWER_WIDTH:question_end]),
        program_id=text(row[question_end], "members.program_id"),
        prior_answer_seq=optional_integer(row[question_end + 1], "prior answer seq"),
    )


class MarkerMove(StrEnum):
    """How an attempt to advance the marker ended."""

    MOVED = "moved"
    UNCHANGED = "unchanged"
    BEYOND_LAST_RECORD = "beyond_last_record"


@dataclass(frozen=True)
class MarkerResult:
    """The marker before and after an attempt; equal unless it ``moved``."""

    move: MarkerMove
    previous: int
    current: int


def advance_marker(store: Store, through: int) -> MarkerResult:
    """Raise the marker to ``through``, never lower it.

    One ``BEGIN IMMEDIATE`` transaction. ``through`` above the last answer's ``seq``
    (0 when there are no answers) writes nothing: the caller has not seen it.
    """
    with store.write() as transaction:
        previous = read_marker(transaction)
        last = transaction.execute(sql.SELECT_MAX_ANSWER_SEQ).fetchone()
        if last is None:
            raise ValueError("MAX(seq) returned no row")
        if through > integer(last[0], "answers.seq"):
            return MarkerResult(MarkerMove.BEYOND_LAST_RECORD, previous, previous)
        transaction.execute(sql.RAISE_MARKER, (through,))
        current = read_marker(transaction)
    move = MarkerMove.MOVED if current > previous else MarkerMove.UNCHANGED
    return MarkerResult(move, previous, current)
