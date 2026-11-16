"""What the push watcher reads (slice 241, D2, D4).

Reads only: nothing is written and no marker is kept, so the watcher never hides mail
from another reader.
"""

from __future__ import annotations

from typing import Final

from amoeba.store import sql_messages
from amoeba.store.models import PushRow
from amoeba.store.row_values import integer, text, vocabulary
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import DeliveryEvent, MessageKind

#: What ``member_high_seq`` answers for a member with no delivery yet. Every
#: assigned ``seq`` is above it, so the watcher takes it as a real baseline.
NO_DELIVERY_SEQ: Final = 0


def member_high_seq(transaction: Transaction, member_id: str) -> int:
    """The member's highest delivery ``seq``, ``NO_DELIVERY_SEQ`` when it has none."""
    row = transaction.execute(
        sql_messages.SELECT_MEMBER_HIGH_SEQ, (member_id,)
    ).fetchone()
    if row is None or row[0] is None:
        return NO_DELIVERY_SEQ
    return integer(row[0], "deliveries.seq")


def push_rows_after(
    transaction: Transaction, member_id: str, after_seq: int
) -> tuple[PushRow, ...]:
    """The member's deliveries with ``seq > after_seq``, in ``seq`` order."""
    rows = transaction.execute(
        sql_messages.SELECT_PUSH_ROWS_AFTER, (member_id, after_seq)
    ).fetchall()
    return tuple(
        PushRow(
            seq=integer(row[0], "deliveries.seq"),
            event=vocabulary(row[1], DeliveryEvent, "deliveries.event"),
            kind=vocabulary(row[2], MessageKind, "messages.kind"),
            counterparty=text(row[3], "messages.from_member"),
        )
        for row in rows
    )
