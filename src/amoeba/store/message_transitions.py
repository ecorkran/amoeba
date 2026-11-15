"""The one writer of a request's state (240 D5, D10).

``reply``, ``cancel``, the expiry sweep and the removal cascade all change state here,
so the rule for who is told is written once: one delivery to each party except the
actor, skipping a party that is no longer an active member. The caller holds the write
transaction, so the change and its deliveries commit together or not at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from amoeba.store import programs, sql_messages
from amoeba.store.deliveries import write_delivery
from amoeba.store.messages import get_message, message_from_row
from amoeba.store.models import Message
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import DeliveryEvent, MessageKind, RequestState

#: ``reason`` written when a member's removal cancels its requests (240 D10).
MEMBER_REMOVED_REASON = "member_removed"


@dataclass(frozen=True)
class StateFields:
    """What a state change sets beyond the state; ``None`` keeps the stored value."""

    result: str | None = None
    result_commit: str | None = None
    result_version: str | None = None
    reason: str | None = None
    accepted_at: datetime | None = None


def change_state(
    transaction: Transaction,
    message: Message,
    new_state: RequestState,
    event: DeliveryEvent,
    actor: str | None,
    now: datetime,
    fields: StateFields,
) -> Message:
    """Move ``message`` to ``new_state`` and tell the parties; returns the new row.

    ``actor`` is the member who made the change and is not told; ``None`` (an unknown
    actor, expiry, the cascade) tells both parties. A party that is not an active
    member is skipped.
    """
    if message.kind is not MessageKind.REQUEST or message.to_member is None:
        raise ValueError(f"{message.message_id} is not a request; it has no state")
    transaction.execute(
        sql_messages.UPDATE_STATE,
        (
            new_state.value,
            fields.result,
            fields.result_commit,
            fields.result_version,
            fields.reason,
            None
            if fields.accepted_at is None
            else encode_timestamp(fields.accepted_at),
            encode_timestamp(now),
            message.message_id,
        ),
    )
    for party in (message.from_member, message.to_member):
        if party == actor or programs.get_member(transaction, party) is None:
            continue
        write_delivery(transaction, party, message.message_id, event, now)
    changed = get_message(transaction, message.message_id)
    if changed is None:
        raise AssertionError(f"request {message.message_id} missing after its update")
    return changed


def cancel_member_requests(
    transaction: Transaction, member_id: str, now: datetime
) -> None:
    """Cancel every live request the member sent or received (240 D10).

    Reason ``member_removed``, told to whichever party is still an active member, so
    call it after the member is removed.
    """
    rows = transaction.execute(
        sql_messages.SELECT_LIVE_REQUESTS_OF, (member_id, member_id)
    ).fetchall()
    for row in rows:
        change_state(
            transaction,
            message_from_row(row),
            RequestState.CANCELLED,
            DeliveryEvent.CANCELLED,
            None,
            now,
            StateFields(reason=MEMBER_REMOVED_REASON),
        )
