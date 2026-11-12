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
    answer_from_row,
    answers_of,
    automatic_answer_count,
    get_answer,
    latest_answer,
    mark_not_delivered,
    mark_resume_started,
    pm_precedent,
    record_resume,
    retract_answer,
    settle_answered,
)
from amoeba.store.models import AnswerRecord, QuestionKey, QuestionRecord
from amoeba.store.question_closing import (
    close_question,
    dismiss_question,
    member_open_questions,
    open_rows_of_run,
    sweep_candidates,
)
from amoeba.store.question_json import serialize_evidence, serialize_passages
from amoeba.store.question_rows import question_from_row
from amoeba.store.row_values import encode_timestamp
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
    "close_question",
    "dismiss_question",
    "find_question",
    "get_answer",
    "get_question",
    "insert_question",
    "latest_answer",
    "latest_question",
    "latest_rows_by_run",
    "mark_not_delivered",
    "mark_resume_started",
    "member_open_questions",
    "open_questions",
    "open_rows_of_run",
    "pm_precedent",
    "question_from_row",
    "record_resume",
    "replace_claim",
    "retract_answer",
    "settle_answered",
    "settle_waiting",
    "sweep_candidates",
]


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


def find_question(
    transaction: Transaction, run_id: str, paused_at: str | None
) -> QuestionRecord | None:
    """The question at ``paused_at``, or the run's latest when it is ``None``."""
    if paused_at is not None:
        return get_question(transaction, QuestionKey(run_id, paused_at))
    return latest_question(transaction, run_id)


def open_questions(
    transaction: Transaction, member_ids: Sequence[str]
) -> tuple[QuestionRecord, ...]:
    """Every ``waiting_on_pm`` question of these members, oldest first by
    ``claimed_at``."""
    if not member_ids:
        return ()
    rows = transaction.execute(
        sql.select_open_questions(len(member_ids)),
        (QuestionState.WAITING_ON_PM.value, *member_ids),
    ).fetchall()
    return tuple(question_from_row(row) for row in rows)


def latest_rows_by_run(
    transaction: Transaction, member_ids: Sequence[str]
) -> dict[str, tuple[QuestionRecord, AnswerRecord | None]]:
    """For each run that has a question of these members, the run's latest question
    (by ``claimed_at``) and that question's latest answer, keyed by ``run_id``.

    A run id is not known until ``sq`` is asked, so this reads every run of the
    members; a run with no entry has no row.
    """
    if not member_ids:
        return {}
    rows = transaction.execute(
        sql.select_member_questions(len(member_ids)), tuple(member_ids)
    ).fetchall()
    latest: dict[str, QuestionRecord] = {}
    for row in rows:
        record = question_from_row(row)
        latest[record.key.run_id] = record  # oldest first: the last one wins
    if not latest:
        return {}
    answer_rows = transaction.execute(
        sql.select_answers_of_runs(len(latest)), tuple(latest)
    ).fetchall()
    newest: dict[QuestionKey, AnswerRecord] = {}
    for answer_row in answer_rows:
        answer = answer_from_row(answer_row)
        newest[answer.key] = answer  # seq order: the last one wins
    return {
        run_id: (record, newest.get(record.key)) for run_id, record in latest.items()
    }


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
