"""``inbox``: a member's requests and notes, and what changed since a delivery number
(slice 240, D7; slice 243, D4).

One read transaction: no write, no read marker, no sweep. Every read applies
``effective_state``, so an open request past its expiry shows ``expired`` at once. The
caller keeps ``as_of_seq`` and passes it back as ``since``, so two worktrees of one
member each see every delivery after their own point.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from amoeba.operations.deps import Deps
from amoeba.operations.message_document import declared_text
from amoeba.operations.message_member import Refusal, resolve_caller
from amoeba.operations.message_models import InboxOutcome, InboxRequest
from amoeba.operations.message_results import (
    DeliveryView,
    InboxResult,
    NoteView,
    RequestDirection,
    RequestView,
)
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.operations.reject_codes import RejectCode, validation_problems
from amoeba.store.deliveries import deliveries_since, highest_assigned_seq
from amoeba.store.messages import requests_changed_since, requests_of
from amoeba.store.models import Message
from amoeba.store.notes import received_notes
from amoeba.store.store import Store, Transaction

__all__ = ["InboxResult", "inbox"]


def inbox(
    store: Store, document: object, *, directory: Path, deps: Deps
) -> InboxResult:
    """The inbox of the member ``directory`` belongs to.

    Raises:
        ContextForgeError: ``cf`` failed or timed out.
        StoreError: The store cannot be used.
    """
    now = deps.clock()
    caller = resolve_caller(
        store, directory, declared_text(document, "member"), deps.cf_run
    )
    if isinstance(caller, Refusal):
        return InboxResult.rejected(caller.code, (caller.detail,), since=None)
    try:
        request = InboxRequest.model_validate(document)
    except ValidationError as error:
        return InboxResult.rejected(
            RejectCode.MALFORMED, validation_problems(error), since=None
        )
    with store.read() as transaction:
        return _read(transaction, caller.member_id, request, now)


def _read(
    transaction: Transaction, member: str, request: InboxRequest, now: datetime
) -> InboxResult:
    as_of_seq = highest_assigned_seq(transaction)
    since = request.since
    if since is not None and since > as_of_seq:
        detail = (
            f"since {since} is beyond the last record, {as_of_seq}; "
            "call inbox without since"
        )
        return InboxResult.rejected(
            RejectCode.BEYOND_LAST_RECORD, (detail,), since=since
        )
    if since is None:
        held = requests_of(transaction, member)
        deliveries = ()
    else:
        held = requests_changed_since(transaction, member, since, now)
        deliveries = deliveries_since(transaction, member, since)
    # Notes come through the member's own deliveries, so ``deliveries`` already holds
    # each note's ``sent`` row when ``since`` is given.
    notes = received_notes(transaction, member, since)
    return InboxResult(
        outcome=InboxOutcome.LISTED,
        notice=QUOTED_DATA_NOTICE,
        rejection=None,
        member=member,
        since=since,
        as_of_seq=as_of_seq,
        requests=tuple(_view(message, member, now) for message in held),
        notes=tuple(NoteView.from_message(item.note) for item in notes),
        deliveries=tuple(DeliveryView.from_delivery(item) for item in deliveries),
        problems=(),
    )


def _view(message: Message, member: str, now: datetime) -> RequestView:
    direction = (
        RequestDirection.SENT
        if message.from_member == member
        else RequestDirection.RECEIVED
    )
    return RequestView.from_message(message, now, direction)
