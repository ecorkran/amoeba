"""Requests: the row mapping, the one by-id read and the effective state (240 D4).

Every function takes the caller's open transaction and a ``now``; nothing here reads
the clock or the config. State changes go through ``message_transitions``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from amoeba.store import sql_messages
from amoeba.store.models import Message
from amoeba.store.row_values import (
    decode_timestamp,
    encode_timestamp,
    integer,
    optional_text,
    optional_timestamp,
    text,
    vocabulary,
)
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import MessageKind, RequestState

#: The depth of a request with no parent (240 D8).
ROOT_DEPTH = 1


def message_from_row(row: tuple[object, ...]) -> Message:
    """A ``messages`` row in ``sql_messages`` select order."""
    state = None if row[9] is None else vocabulary(row[9], RequestState, "state")
    return Message(
        message_id=text(row[0], "messages.message_id"),
        kind=vocabulary(row[1], MessageKind, "messages.kind"),
        from_member=text(row[2], "messages.from_member"),
        to_member=optional_text(row[3], "messages.to_member"),
        to_program=optional_text(row[4], "messages.to_program"),
        parent_id=optional_text(row[5], "messages.parent_id"),
        depth=integer(row[6], "messages.depth"),
        subject=text(row[7], "messages.subject"),
        body=text(row[8], "messages.body"),
        state=state,
        result=optional_text(row[10], "messages.result"),
        result_commit=optional_text(row[11], "messages.result_commit"),
        result_version=optional_text(row[12], "messages.result_version"),
        reason=optional_text(row[13], "messages.reason"),
        accepted_at=optional_timestamp(row[14], "messages.accepted_at"),
        created_at=decode_timestamp(row[15], "messages.created_at"),
        state_changed_at=decode_timestamp(row[16], "messages.state_changed_at"),
        expires_at=optional_timestamp(row[17], "messages.expires_at"),
    )


def get_message(transaction: Transaction, message_id: str) -> Message | None:
    """The message with this id, or ``None``. The one by-id read of a request."""
    row = transaction.execute(sql_messages.SELECT_MESSAGE, (message_id,)).fetchone()
    return None if row is None else message_from_row(row)


def effective_state(message: Message, now: datetime) -> RequestState | None:
    """The state every read shows: an ``open`` request at or past ``expires_at`` is
    ``expired`` before the sweep records it. A note has no state (``None``).
    """
    if message.state is RequestState.OPEN and message.expires_at is not None:
        if message.expires_at <= now:
            return RequestState.EXPIRED
    return message.state


def requests_of(transaction: Transaction, member_id: str) -> tuple[Message, ...]:
    """Every request the member sent or received that the store still holds."""
    rows = transaction.execute(
        sql_messages.SELECT_REQUESTS_OF, (member_id, member_id)
    ).fetchall()
    return tuple(message_from_row(row) for row in rows)


def live_requests_of(transaction: Transaction, member_id: str) -> tuple[Message, ...]:
    """The requests the member sent or received that can still change (stored state
    ``open`` or ``accepted``), oldest first. Read ``effective_state`` for each."""
    rows = transaction.execute(
        sql_messages.SELECT_LIVE_REQUESTS_OF, (member_id, member_id)
    ).fetchall()
    return tuple(message_from_row(row) for row in rows)


def live_children_of_member(
    transaction: Transaction, member_id: str
) -> dict[str, tuple[str, ...]]:
    """For each live request the member sent or received that has live children, the
    ids of those children (the live requests naming it as ``parent_id``), oldest
    first. One read for all of the member's requests."""
    rows = transaction.execute(
        sql_messages.SELECT_LIVE_CHILDREN_OF_MEMBER, (member_id, member_id)
    )
    children: dict[str, list[str]] = {}
    for row in rows:
        parent = text(row[0], "messages.parent_id")
        children.setdefault(parent, []).append(text(row[1], "messages.message_id"))
    return {parent: tuple(ids) for parent, ids in children.items()}


def requests_changed_since(
    transaction: Transaction, member_id: str, since: int, now: datetime
) -> tuple[Message, ...]:
    """The member's requests that its deliveries after ``since`` concern (each once),
    and its open requests past ``expires_at`` that the sweep has not yet recorded."""
    rows = transaction.execute(
        sql_messages.SELECT_REQUESTS_CHANGED_SINCE,
        (member_id, since, encode_timestamp(now), member_id, member_id),
    ).fetchall()
    return tuple(message_from_row(row) for row in rows)


def request_counts_from(transaction: Transaction, member_id: str) -> tuple[int, int]:
    """``(all, live)``: the requests the member sent that the store holds, and how many
    of them can still change (``open`` or ``accepted``)."""
    row = transaction.execute(sql_messages.COUNT_REQUESTS_FROM, (member_id,)).fetchone()
    if row is None:
        raise AssertionError("a count returned no row")
    return integer(row[0], "count"), integer(row[1], "live count")


def prune_oldest_finished_from(
    transaction: Transaction, member_id: str, count: int
) -> None:
    """Delete the member's ``count`` oldest finished requests, deliveries first."""
    rows = transaction.execute(
        sql_messages.SELECT_OLDEST_TERMINAL_FROM, (member_id, count)
    ).fetchall()
    for row in rows:
        message_id = text(row[0], "messages.message_id")
        transaction.execute(sql_messages.DELETE_DELIVERIES_OF, (message_id,))
        transaction.execute(sql_messages.DELETE_MESSAGE, (message_id,))


def insert_request(
    transaction: Transaction,
    *,
    message_id: str,
    from_member: str,
    to_member: str,
    parent_id: str | None,
    parent_depth: int | None,
    subject: str,
    body: str,
    ttl: timedelta,
    now: datetime,
) -> Message:
    """Store a new ``open`` request and return it.

    ``depth`` is the parent's plus one (``parent_depth`` is ``None`` for a root) and
    ``expires_at`` is ``now + ttl``; the caller passes both from what it already read
    and from the config, because the store holds neither.
    """
    depth = ROOT_DEPTH if parent_depth is None else parent_depth + 1
    stamp = encode_timestamp(now)
    transaction.execute(
        sql_messages.INSERT_REQUEST,
        (
            message_id,
            MessageKind.REQUEST.value,
            from_member,
            to_member,
            parent_id,
            depth,
            subject,
            body,
            RequestState.OPEN.value,
            stamp,
            stamp,
            encode_timestamp(now + ttl),
        ),
    )
    stored = get_message(transaction, message_id)
    if stored is None:
        raise AssertionError(f"request {message_id} missing after its insert")
    return stored
