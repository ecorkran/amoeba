"""Question reads, the claim insert and the compare-and-set moves (slice 223, D4, D10).

Every function takes an open transaction (``Store.read()`` or ``Store.write()``);
none is held across a subprocess. Every move out of ``claimed`` names the claim it
holds (``answering_run_id``), so nobody settles a claim they do not hold. The answer
functions live in ``store.answers`` and are re-exported here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from amoeba.answering.values import AnsweringEvidence, DeclineReason, PassageRef
from amoeba.store import sql
from amoeba.store.answers import (
    Lost,
    Settled,
    add_pm_answer,
    answers_of,
    automatic_answer_count,
    get_answer,
    latest_answer,
    pm_precedent,
    record_resume,
    settle_answered,
)
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.question_json import (
    parse_evidence,
    parse_passages,
    serialize_evidence,
    serialize_passages,
)
from amoeba.store.row_values import (
    decode_timestamp,
    encode_timestamp,
    optional_text,
    text,
    vocabulary,
)
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import QuestionState

__all__ = [
    "Lost",
    "NewQuestion",
    "Settled",
    "add_pm_answer",
    "any_answering_run_id",
    "answers_of",
    "automatic_answer_count",
    "get_answer",
    "get_question",
    "insert_question",
    "latest_answer",
    "latest_question",
    "pm_precedent",
    "record_resume",
    "replace_claim",
    "settle_answered",
    "settle_waiting",
]


def question_from_row(row: Sequence[object]) -> QuestionRecord:
    """A ``QuestionRecord`` from a row of ``sql.QUESTION_COLUMNS``."""
    return QuestionRecord(
        key=QuestionKey(
            run_id=text(row[0], "questions.run_id"),
            paused_at=text(row[1], "questions.paused_at"),
        ),
        member_id=text(row[2], "questions.member_id"),
        question=text(row[3], "questions.question"),
        checkout=text(row[4], "questions.checkout"),
        state=vocabulary(row[5], QuestionState, "questions.state"),
        answering_run_id=optional_text(row[6], "questions.answering_run_id"),
        waiting_reason=(
            None
            if row[7] is None
            else vocabulary(row[7], DeclineReason, "questions.waiting_reason")
        ),
        waiting_detail=optional_text(row[8], "questions.waiting_detail"),
        slice_label=optional_text(row[9], "questions.slice_label"),
        source_commit=optional_text(row[10], "questions.source_commit"),
        passages=None if row[11] is None else parse_passages(row[11]),
        evidence=None if row[12] is None else parse_evidence(row[12]),
        claimed_at=decode_timestamp(row[13], "questions.claimed_at"),
        updated_at=decode_timestamp(row[14], "questions.updated_at"),
    )


# --- reads ------------------------------------------------------------------


def get_question(transaction: Transaction, key: QuestionKey) -> QuestionRecord | None:
    row = transaction.execute(
        sql.SELECT_QUESTION, (key.run_id, key.paused_at)
    ).fetchone()
    return None if row is None else question_from_row(row)


def latest_question(transaction: Transaction, run_id: str) -> QuestionRecord | None:
    """The run's question with the latest ``claimed_at``."""
    row = transaction.execute(sql.SELECT_LATEST_QUESTION, (run_id,)).fetchone()
    return None if row is None else question_from_row(row)


def any_answering_run_id(transaction: Transaction, run_id: str) -> bool:
    """Whether some question's claim is this run, i.e. it is an answering run."""
    row = transaction.execute(sql.SELECT_ANSWERING_RUN_EXISTS, (run_id,)).fetchone()
    return row is not None


# --- writes -----------------------------------------------------------------


@dataclass(frozen=True)
class NewQuestion:
    """A first sighting of a question: claimed (with its answering run) or waiting
    on the PM (with its reason). Exactly one of the two is set."""

    key: QuestionKey
    member_id: str
    question: str
    checkout: str
    slice_label: str | None
    source_commit: str | None
    passages: tuple[PassageRef, ...] | None
    answering_run_id: str | None
    waiting_reason: DeclineReason | None
    waiting_detail: str | None

    def __post_init__(self) -> None:
        if (self.answering_run_id is None) == (self.waiting_reason is None):
            raise ValueError(
                "a new question is claimed (answering_run_id) or waiting "
                "(waiting_reason), not both or neither"
            )

    @property
    def state(self) -> QuestionState:
        if self.answering_run_id is not None:
            return QuestionState.CLAIMED
        return QuestionState.WAITING_ON_PM


def insert_question(
    transaction: Transaction, new: NewQuestion, *, now: datetime
) -> bool:
    """Insert the row unless one exists for the key; True if this call wrote it, so
    the caller is the claimant."""
    moment = encode_timestamp(now)
    cursor = transaction.execute(
        sql.INSERT_NEW_QUESTION,
        (
            new.key.run_id,
            new.key.paused_at,
            new.member_id,
            new.question,
            new.checkout,
            new.state.value,
            new.answering_run_id,
            None if new.waiting_reason is None else new.waiting_reason.value,
            new.waiting_detail,
            new.slice_label,
            new.source_commit,
            None if new.passages is None else serialize_passages(new.passages),
            moment,
            moment,
        ),
    )
    return cursor.rowcount == 1


def settle_waiting(
    transaction: Transaction,
    key: QuestionKey,
    answering_run_id: str,
    *,
    reason: DeclineReason,
    detail: str | None,
    evidence: AnsweringEvidence | None,
    now: datetime,
) -> bool:
    """``claimed -> waiting_on_pm`` for the claim ``answering_run_id`` holds; True if
    a row changed."""
    cursor = transaction.execute(
        sql.SETTLE_WAITING,
        (
            QuestionState.WAITING_ON_PM.value,
            reason.value,
            detail,
            None if evidence is None else serialize_evidence(evidence),
            encode_timestamp(now),
            key.run_id,
            key.paused_at,
            QuestionState.CLAIMED.value,
            answering_run_id,
        ),
    )
    return cursor.rowcount == 1


def replace_claim(
    transaction: Transaction,
    key: QuestionKey,
    *,
    old_answering_run_id: str,
    new_answering_run_id: str,
    passages: tuple[PassageRef, ...],
    now: datetime,
) -> bool:
    """Swap a dead claim's answering run id and passages for a new one (D7,
    ``not_found`` and old); True if a row changed."""
    cursor = transaction.execute(
        sql.REPLACE_CLAIM,
        (
            new_answering_run_id,
            serialize_passages(passages),
            encode_timestamp(now),
            key.run_id,
            key.paused_at,
            QuestionState.CLAIMED.value,
            old_answering_run_id,
        ),
    )
    return cursor.rowcount == 1
