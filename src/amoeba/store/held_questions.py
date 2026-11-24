"""Questions held on a request: the insert, the reads and the moves out (slice 242,
D2, D3).

Every function takes an open transaction; none is held across a subprocess. A
``BadLink`` question is not held: it is inserted ``waiting_on_pm`` through
``questions.insert_question``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from amoeba.answering.values import DeclineReason, PassageRef
from amoeba.store import sql_held
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.question_json import serialize_passages
from amoeba.store.question_rows import question_from_row
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import QuestionState


@dataclass(frozen=True)
class HeldQuestion:
    """A first sighting of a question that names a request: no claim and no reason
    yet, so it is not a ``NewQuestion``."""

    key: QuestionKey
    member_id: str
    question: str
    checkout: str


def insert_held(
    transaction: Transaction, new: HeldQuestion, request_id: str, now: datetime
) -> bool:
    """Insert the held row unless one exists for the key; True if this call wrote
    it."""
    moment = encode_timestamp(now)
    acting = transaction.acting("questions")
    cursor = transaction.execute(
        sql_held.INSERT_HELD,
        (
            new.key.run_id,
            new.key.paused_at,
            new.member_id,
            new.question,
            new.checkout,
            QuestionState.WAITING_ON_REQUEST.value,
            request_id,
            moment,
            moment,
            acting.owner_id,
            acting.machine_id,
        ),
    )
    return cursor.rowcount == 1


def held_rows(transaction: Transaction) -> list[QuestionRecord]:
    """Every ``waiting_on_request`` row, oldest first."""
    rows = transaction.execute(
        sql_held.SELECT_HELD_ROWS, (QuestionState.WAITING_ON_REQUEST.value,)
    ).fetchall()
    return [question_from_row(row) for row in rows]


def claim_held(  # noqa: PLR0913 - the claim's named columns, D3
    transaction: Transaction,
    key: QuestionKey,
    *,
    answering_run_id: str,
    passages: tuple[PassageRef, ...],
    slice_label: str,
    source_commit: str,
    now: datetime,
) -> bool:
    """``waiting_on_request -> claimed``, resetting ``claimed_at`` and
    ``updated_at`` so the dead-claim rules age the claim from now; True if this call
    moved the row."""
    moment = encode_timestamp(now)
    cursor = transaction.execute(
        sql_held.CLAIM_HELD,
        (
            QuestionState.CLAIMED.value,
            answering_run_id,
            serialize_passages(passages),
            slice_label,
            source_commit,
            moment,
            moment,
            key.run_id,
            key.paused_at,
            QuestionState.WAITING_ON_REQUEST.value,
        ),
    )
    return cursor.rowcount == 1


def settle_held_waiting(
    transaction: Transaction,
    key: QuestionKey,
    *,
    reason: DeclineReason,
    detail: str | None,
    now: datetime,
) -> bool:
    """``waiting_on_request -> waiting_on_pm`` with the reason; ``claimed_at`` stays
    the hold time. True if this call moved the row."""
    cursor = transaction.execute(
        sql_held.SETTLE_HELD_WAITING,
        (
            QuestionState.WAITING_ON_PM.value,
            reason.value,
            detail,
            encode_timestamp(now),
            key.run_id,
            key.paused_at,
            QuestionState.WAITING_ON_REQUEST.value,
        ),
    )
    return cursor.rowcount == 1


def mark_start_attempted(
    transaction: Transaction,
    key: QuestionKey,
    now: datetime,
    previous: datetime | None,
) -> bool:
    """Record that ``handle_pause`` is being started for the held row, if its last
    start is still ``previous`` (as the caller read it); ``updated_at`` is left alone.
    True if this call recorded it, so the caller starts the child."""
    cursor = transaction.execute(
        sql_held.MARK_START_ATTEMPTED,
        (
            encode_timestamp(now),
            key.run_id,
            key.paused_at,
            QuestionState.WAITING_ON_REQUEST.value,
            None if previous is None else encode_timestamp(previous),
        ),
    )
    return cursor.rowcount == 1
