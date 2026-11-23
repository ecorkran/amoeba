"""The rows that record a refused call (240 D9)."""

from __future__ import annotations

from datetime import datetime

from amoeba.store import sql_messages
from amoeba.store.models import MessageRejection
from amoeba.store.row_values import (
    decode_timestamp,
    encode_timestamp,
    integer,
    optional_text,
    text,
)
from amoeba.store.store import Transaction


def record_rejection(
    transaction: Transaction,
    member_id: str,
    operation: str,
    to_ref: str | None,
    message_id: str | None,
    parent_id: str | None,
    code: str,
    detail: str,
    now: datetime,
) -> None:
    """One rejection for the caller ``member_id``.

    ``operation`` and ``code`` are an ``OperationName`` and a ``RejectCode`` value;
    the store takes text because it imports nothing from ``operations``.
    """
    transaction.execute(
        sql_messages.INSERT_REJECTION,
        (
            member_id,
            operation,
            to_ref,
            message_id,
            parent_id,
            code,
            detail,
            encode_timestamp(now),
            transaction.acting("message_rejections").owner_id,
        ),
    )


def trim_rejections(transaction: Transaction, member_id: str, keep: int) -> None:
    """Drop the member's oldest rows so that at most ``keep`` remain."""
    transaction.execute(sql_messages.TRIM_REJECTIONS, (member_id, member_id, keep))


def rejections_of(
    transaction: Transaction, member_id: str
) -> tuple[MessageRejection, ...]:
    """The member's retained rejections, newest first."""
    rows = transaction.execute(sql_messages.SELECT_REJECTIONS_OF, (member_id,))
    return tuple(
        MessageRejection(
            id=integer(row[0], "message_rejections.id"),
            member_id=text(row[1], "message_rejections.member_id"),
            operation=text(row[2], "message_rejections.operation"),
            to_ref=optional_text(row[3], "message_rejections.to_ref"),
            message_id=optional_text(row[4], "message_rejections.message_id"),
            parent_id=optional_text(row[5], "message_rejections.parent_id"),
            code=text(row[6], "message_rejections.code"),
            detail=text(row[7], "message_rejections.detail"),
            created_at=decode_timestamp(row[8], "message_rejections.created_at"),
        )
        for row in rows
    )
