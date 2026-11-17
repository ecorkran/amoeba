"""Deliveries: what a member should learn about a request (240 D5, D7).

Each row takes the next autoincrement ``seq``. Pruning deletes rows, but
``sqlite_sequence`` keeps the highest number ever assigned, which ``inbox`` hands back
as ``as_of_seq``.
"""

from __future__ import annotations

from datetime import datetime

from amoeba.store import sql_messages
from amoeba.store.models import Delivery
from amoeba.store.row_values import (
    decode_timestamp,
    encode_timestamp,
    integer,
    text,
    vocabulary,
)
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import DeliveryEvent

#: What ``highest_assigned_seq`` answers before any delivery was ever written.
NONE_ASSIGNED = 0


def write_delivery(
    transaction: Transaction,
    member_id: str,
    message_id: str,
    event: DeliveryEvent,
    now: datetime,
) -> None:
    """One delivery for ``member_id``; its ``seq`` is the next one."""
    transaction.execute(
        sql_messages.INSERT_DELIVERY,
        (member_id, message_id, event.value, encode_timestamp(now)),
    )


def deliveries_since(
    transaction: Transaction, member_id: str, since: int
) -> tuple[Delivery, ...]:
    """The member's deliveries with ``seq > since``, oldest first."""
    rows = transaction.execute(
        sql_messages.SELECT_DELIVERIES_SINCE, (member_id, since)
    ).fetchall()
    return tuple(delivery_from_row(row) for row in rows)


def highest_assigned_seq(transaction: Transaction) -> int:
    """The highest ``seq`` ever assigned, ``NONE_ASSIGNED`` when there is none.

    Read from ``sqlite_sequence``, so pruning delivery rows never lowers it.
    """
    row = transaction.execute(sql_messages.SELECT_HIGHEST_ASSIGNED_SEQ).fetchone()
    return NONE_ASSIGNED if row is None else integer(row[0], "sqlite_sequence.seq")


def delivery_from_row(row: tuple[object, ...]) -> Delivery:
    return Delivery(
        seq=integer(row[0], "deliveries.seq"),
        member_id=text(row[1], "deliveries.member_id"),
        message_id=text(row[2], "deliveries.message_id"),
        event=vocabulary(row[3], DeliveryEvent, "deliveries.event"),
        created_at=decode_timestamp(row[4], "deliveries.created_at"),
    )
