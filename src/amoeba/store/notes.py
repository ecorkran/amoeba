"""Notes: one-way messages with no state (slice 243, D1, D2, D6).

A note is a ``messages`` row of kind ``note`` plus one ``sent`` delivery per recipient.
It has no state, no expiry and no chain: ``state`` and ``expires_at`` are null,
``state_changed_at`` equals ``created_at`` and ``depth`` is the column's minimum. Its
only exit is the prune. Every function takes the caller's open transaction and a ``now``
or a cutoff; nothing here reads the clock or the config.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from amoeba.store import sql_messages
from amoeba.store.deliveries import delivery_from_row, write_delivery
from amoeba.store.messages import (
    ROOT_DEPTH,
    delete_with_deliveries,
    get_message,
    message_from_row,
)
from amoeba.store.models import Delivery, Message
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import DeliveryEvent, MessageKind

#: ``received_notes`` without ``since``: every delivery has ``seq`` of 1 or more.
FROM_THE_START = 0


@dataclass(frozen=True)
class NewNote:
    """What a note's writer supplies: one of ``to_member`` and ``to_program``."""

    message_id: str
    from_member: str
    to_member: str | None
    to_program: str | None
    subject: str
    body: str


@dataclass(frozen=True)
class ReceivedNote:
    """A note a member has a delivery for, beside that ``sent`` delivery."""

    note: Message
    delivery: Delivery


def insert_note(
    transaction: Transaction,
    note: NewNote,
    recipient_ids: Sequence[str],
    now: datetime,
) -> Message:
    """Store ``note`` and one ``sent`` delivery per recipient, in the order given.

    Each delivery takes the next ``seq``. A raise leaves it to the caller's
    transaction to roll the row and the deliveries back together.
    """
    stamp = encode_timestamp(now)
    transaction.execute(
        sql_messages.INSERT_NOTE,
        (
            note.message_id,
            MessageKind.NOTE.value,
            note.from_member,
            note.to_member,
            note.to_program,
            ROOT_DEPTH,
            note.subject,
            note.body,
            stamp,
            stamp,
        ),
    )
    for recipient in recipient_ids:
        write_delivery(transaction, recipient, note.message_id, DeliveryEvent.SENT, now)
    stored = get_message(transaction, note.message_id)
    if stored is None:
        raise AssertionError(f"note {note.message_id} missing after its insert")
    return stored


def received_notes(
    transaction: Transaction, member_id: str, since: int | None
) -> tuple[ReceivedNote, ...]:
    """The notes ``member_id`` has a delivery for, in delivery order.

    With ``since``, only those whose delivery has ``seq > since``. A note has one
    delivery per recipient and no later change, so each appears once.
    """
    after = FROM_THE_START if since is None else since
    rows = transaction.execute(
        sql_messages.SELECT_RECEIVED_NOTES, (member_id, after)
    ).fetchall()
    return tuple(
        ReceivedNote(
            note=message_from_row(row[: sql_messages.MESSAGE_COLUMN_COUNT]),
            delivery=delivery_from_row(row[sql_messages.MESSAGE_COLUMN_COUNT :]),
        )
        for row in rows
    )


def prune_notes(transaction: Transaction, cutoff: str) -> int:
    """Delete the notes created before ``cutoff`` and their deliveries; the count.

    ``cutoff`` is an encoded timestamp, as the request prune takes. Requests are
    never touched.
    """
    transaction.execute(sql_messages.DELETE_PRUNABLE_NOTE_DELIVERIES, (cutoff,))
    return transaction.execute(sql_messages.DELETE_PRUNABLE_NOTES, (cutoff,)).rowcount


def prune_oldest_notes_from(
    transaction: Transaction, member_id: str, keep: int
) -> None:
    """Delete all but the newest ``keep`` notes ``member_id`` sent, deliveries first.

    Other senders' notes and every request are untouched.
    """
    delete_with_deliveries(
        transaction, sql_messages.SELECT_NOTES_BEYOND_NEWEST_FROM, (member_id, keep)
    )
