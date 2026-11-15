"""The requests and rejected calls ``status`` and ``list`` show under a member (slice
240, D12).

One read transaction for every member in scope. Requests are the member's open and
accepted ones, sent and received, each with its effective state and the live requests
that name it as parent (``child_ids``: what it is waiting on).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from amoeba.operations.message_results import RequestDirection
from amoeba.operations.status_models import RejectedCall, RequestEntry
from amoeba.store.message_rejections import rejections_of
from amoeba.store.messages import (
    effective_state,
    live_children_of_member,
    live_requests_of,
)
from amoeba.store.models import Message, MessageRejection
from amoeba.store.store import Store, Transaction


@dataclass(frozen=True)
class MemberMessages:
    """What one member shows: its requests and its rejected calls."""

    requests: tuple[RequestEntry, ...]
    rejected_calls: tuple[RejectedCall, ...]


def read_member_messages(
    store: Store,
    member_ids: Iterable[str],
    names: Mapping[str, str],
    now: datetime,
) -> dict[str, MemberMessages]:
    """Each member's requests and rejected calls, read in one transaction.

    ``names`` maps Context Forge project ids to names; an id it lacks shows no name.
    """
    with store.read() as transaction:
        return {
            member: MemberMessages(
                requests=_requests(transaction, member, names, now),
                rejected_calls=tuple(
                    _rejected_call(row) for row in rejections_of(transaction, member)
                ),
            )
            for member in member_ids
        }


def _requests(
    transaction: Transaction, member: str, names: Mapping[str, str], now: datetime
) -> tuple[RequestEntry, ...]:
    children = live_children_of_member(transaction, member)
    return tuple(
        _request_entry(message, member, children, names, now)
        for message in live_requests_of(transaction, member)
    )


def _request_entry(
    message: Message,
    member: str,
    children: Mapping[str, tuple[str, ...]],
    names: Mapping[str, str],
    now: datetime,
) -> RequestEntry:
    state = effective_state(message, now)
    if state is None or message.to_member is None:
        raise ValueError(f"{message.message_id!r} is not a request")
    sent = message.from_member == member
    other = message.to_member if sent else message.from_member
    return RequestEntry(
        id=message.message_id,
        direction=RequestDirection.SENT if sent else RequestDirection.RECEIVED,
        other_member=other,
        other_name=names.get(other),
        subject=message.subject,
        state=state,
        created_at=message.created_at,
        state_changed_at=message.state_changed_at,
        parent_id=message.parent_id,
        child_ids=children.get(message.message_id, ()),
    )


def _rejected_call(row: MessageRejection) -> RejectedCall:
    return RejectedCall(
        operation=row.operation,
        code=row.code,
        to_ref=row.to_ref,
        message_id=row.message_id,
        parent_id=row.parent_id,
        detail=row.detail,
        created_at=row.created_at,
    )
