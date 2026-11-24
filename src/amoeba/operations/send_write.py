"""``send``: the write transaction (slice 240, D2, D5, D6, D8, D9).

Given the resolved sender and recipient and a validated request, one transaction:
sweep, check the id against an existing row (a retry is answered from it, even when
its parent has since been pruned), then for a new request check the parent and the
chain depth, insert it and write its ``sent`` delivery. A rejection found here writes
its ``message_rejections`` row in the same transaction and commits it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from amoeba.config.user_config import UserConfig
from amoeba.operations.message_models import (
    MAX_REQUESTS_PER_SENDER,
    SendOutcome,
    SendRequest,
)
from amoeba.operations.message_rejection import record_in_transaction
from amoeba.operations.message_results import (
    NoteView,
    RequestDirection,
    RequestView,
    SendResult,
)
from amoeba.operations.names import OperationName
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.operations.reject_codes import NotARequest, RejectCode, as_request
from amoeba.operations.steps.limits import wake_limits
from amoeba.store.deliveries import write_delivery
from amoeba.store.message_sweep import sweep
from amoeba.store.messages import (
    effective_state,
    get_message,
    insert_request,
    prune_oldest_finished_from,
    request_counts_from,
)
from amoeba.store.models import Message
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import DeliveryEvent, MessageKind, RequestState
from amoeba.store.wakes import set_wake_mark


@dataclass(frozen=True)
class SendProblem:
    """Why a ``send`` ends as ``rejected`` once its caller is known."""

    code: RejectCode
    detail: str


def write_send(
    store: Store,
    config: UserConfig,
    *,
    sender: str,
    recipient: str,
    request: SendRequest,
    now: datetime,
) -> SendResult:
    """Store ``request`` from ``sender`` to ``recipient``, or say why not.

    Raises:
        StoreError: The store cannot be used.
    """
    with store.write() as transaction:
        sweep(transaction, now, config.prune_after_days)
        existing = get_message(transaction, request.id)
        if existing is not None:
            return _resend(
                transaction, config, existing, (sender, recipient), request, now
            )
        parent_depth: int | None = None
        if request.parent is not None:
            parent = _check_parent(transaction, request.parent, config)
            if isinstance(parent, SendProblem):
                return reject_send(transaction, sender, request, parent, now)
            parent_depth = parent.depth
        crowded = _make_room(transaction, sender)
        if crowded is not None:
            return reject_send(transaction, sender, request, crowded, now)
        stored = insert_request(
            transaction,
            message_id=request.id,
            from_member=sender,
            to_member=recipient,
            parent_id=request.parent,
            parent_depth=parent_depth,
            subject=request.subject,
            body=request.body,
            ttl=timedelta(hours=config.request_open_ttl_hours),
            now=now,
        )
        write_delivery(
            transaction, recipient, stored.message_id, DeliveryEvent.SENT, now
        )
        # The mark is written here, before any wake claim reads it (262 D8).
        set_wake_mark(
            transaction, stored.message_id, recipient, now, wake_limits(config)
        )
        return sent_result(SendOutcome.SENT, stored, now)


def _make_room(transaction: Transaction, sender: str) -> SendProblem | None:
    """Keep the sender within ``MAX_REQUESTS_PER_SENDER`` once this request is stored.

    The sender's oldest finished requests are dropped to make room; when so many are
    still live that dropping finished ones is not enough, the send is refused. The
    refusal comes first, so nothing is dropped for a send that does not happen.
    """
    held, live = request_counts_from(transaction, sender)
    if live >= MAX_REQUESTS_PER_SENDER:
        return SendProblem(
            RejectCode.TOO_MANY_OPEN,
            f"this member already has {live} requests open or accepted, the most "
            f"allowed ({MAX_REQUESTS_PER_SENDER}); finish or cancel some first",
        )
    excess = held - (MAX_REQUESTS_PER_SENDER - 1)
    if excess > 0:
        prune_oldest_finished_from(transaction, sender, excess)
    return None


def _check_parent(
    transaction: Transaction, parent_id: str, config: UserConfig
) -> Message | SendProblem:
    """The parent row, or why it cannot be a parent: nothing else is checked (D8)."""
    parent = as_request(parent_id, get_message(transaction, parent_id))
    if isinstance(parent, NotARequest):
        return SendProblem(RejectCode.PARENT_UNKNOWN, parent.detail)
    if parent.depth >= config.max_chain_depth:
        return SendProblem(
            RejectCode.CHAIN_TOO_DEEP,
            f"parent {parent_id!r} is already {parent.depth} deep; "
            f"a chain may go {config.max_chain_depth} deep",
        )
    return parent


def _resend(  # noqa: PLR0913 - the transaction, the stored row and the send again
    transaction: Transaction,
    config: UserConfig,
    existing: Message,
    parties: tuple[str, str],
    request: SendRequest,
    now: datetime,
) -> SendResult:
    """D2: the same id again. Same content is a retry; anything else is refused.

    A retry of a request that is still open wants a wake again when today's conditions
    hold, which is how a request sent while a session was live is woken once the
    session is stale (262 D8).
    """
    sender, recipient = parties
    if not same_content(
        existing,
        kind=MessageKind.REQUEST,
        from_member=sender,
        to_member=recipient,
        to_program=None,
        parent_id=request.parent,
        request=request,
    ):
        return reject_send(transaction, sender, request, id_reused(request.id), now)
    state = effective_state(existing, now)
    if state in RequestState.terminal():
        problem = SendProblem(
            RejectCode.REQUEST_ENDED,
            f"request {request.id!r} is already {state.value}; "
            "send it again under a new id",
        )
        return reject_send(transaction, sender, request, problem, now)
    set_wake_mark(transaction, existing.message_id, recipient, now, wake_limits(config))
    return sent_result(SendOutcome.UNCHANGED, existing, now)


def same_content(
    existing: Message,
    *,
    kind: MessageKind,
    from_member: str,
    to_member: str | None,
    to_program: str | None,
    parent_id: str | None,
    request: SendRequest,
) -> bool:
    """D2 and D3 (243): whether ``existing`` is this same message sent again. The one
    comparison, for a request and a note."""
    return (
        existing.kind,
        existing.from_member,
        existing.to_member,
        existing.to_program,
        existing.parent_id,
        existing.subject,
        existing.body,
    ) == (
        kind,
        from_member,
        to_member,
        to_program,
        parent_id,
        request.subject,
        request.body,
    )


def id_reused(message_id: str) -> SendProblem:
    """The id belongs to a message with other content, whoever sent it."""
    return SendProblem(
        RejectCode.ID_REUSED,
        f"the id {message_id!r} belongs to a different message; "
        "send this one under a new id",
    )


def sent_result(outcome: SendOutcome, message: Message, now: datetime) -> SendResult:
    """The result of a stored message: a request view or, for a note, a note view."""
    is_note = message.kind is MessageKind.NOTE
    return SendResult(
        outcome=outcome,
        notice=QUOTED_DATA_NOTICE,
        rejection=None,
        request=(
            None
            if is_note
            else RequestView.from_message(message, now, RequestDirection.SENT)
        ),
        note=NoteView.from_message(message) if is_note else None,
        problems=(),
    )


def reject_send(
    transaction: Transaction,
    sender: str,
    request: SendRequest,
    problem: SendProblem,
    now: datetime,
) -> SendResult:
    """Record the rejection under ``sender`` in this transaction; it commits."""
    record_in_transaction(
        transaction,
        sender,
        OperationName.SEND.value,
        now,
        to_ref=request.recipient_ref,
        message_id=request.id,
        parent_id=request.parent,
        code=problem.code,
        detail=problem.detail,
    )
    return SendResult.rejected(problem.code, (problem.detail,))
