"""``reply``: the addressee accepts, declines or finishes a request (slice 240, D4, D5,
D9).

The caller is resolved and the document validated before any store lock. One write
transaction then sweeps, loads the request and applies the D4 table; every state change
goes through ``change_state``, which writes the deliveries. A refusal is recorded under
the caller, in the transaction that found it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import ValidationError

from amoeba.config.user_config import UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.message_document import declared_text
from amoeba.operations.message_member import Refusal, caller_of
from amoeba.operations.message_models import (
    ReplyAction,
    ReplyOutcome,
    ReplyRequest,
)
from amoeba.operations.message_rejection import (
    record_declared,
    record_in_transaction,
)
from amoeba.operations.message_results import (
    ReplyResult,
    RequestDirection,
    RequestView,
)
from amoeba.operations.names import OperationName
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.operations.reject_codes import (
    NotARequest,
    RejectCode,
    as_request,
    validation_problems,
)
from amoeba.store.message_sweep import sweep
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import effective_state, get_message
from amoeba.store.models import Message
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, RequestState

__all__ = ["ReplyResult", "reply"]

#: The states each action may start from (D4).
_ALLOWED_FROM: Final = {
    ReplyAction.ACCEPT: frozenset({RequestState.OPEN}),
    ReplyAction.DECLINE: frozenset({RequestState.OPEN, RequestState.ACCEPTED}),
    ReplyAction.DONE: frozenset({RequestState.ACCEPTED}),
}
#: The state each action leads to, and the event the sender is told.
_RESULT: Final = {
    ReplyAction.ACCEPT: (RequestState.ACCEPTED, DeliveryEvent.ACCEPTED),
    ReplyAction.DECLINE: (RequestState.DECLINED, DeliveryEvent.DECLINED),
    ReplyAction.DONE: (RequestState.DONE, DeliveryEvent.DONE),
}


def reply(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    here: HereCaller | HereNotAProject,
    deps: Deps,
) -> ReplyResult:
    """Apply the reply in ``document`` for the member whose checkout ``here`` is.

    Raises:
        StoreError: The store cannot be used.
    """
    now = deps.clock()
    caller = caller_of(store, here, declared_text(document, "member"))
    if isinstance(caller, Refusal):
        record_declared(store, caller, OperationName.REPLY.value, document, now)
        return ReplyResult.rejected(caller.code, (caller.detail,))
    try:
        request = ReplyRequest.model_validate(document)
    except ValidationError as error:
        problems = validation_problems(error)
        malformed = Refusal(RejectCode.MALFORMED, "; ".join(problems), caller.member_id)
        record_declared(store, malformed, OperationName.REPLY.value, document, now)
        return ReplyResult.rejected(RejectCode.MALFORMED, problems)
    return _apply(store, config, request, caller.member_id, now)


def _apply(
    store: Store,
    config: UserConfig,
    request: ReplyRequest,
    caller: str,
    now: datetime,
) -> ReplyResult:
    with store.write() as transaction:
        sweep(transaction, now, config.prune_after_days)
        message = get_message(transaction, request.id)
        problem = _problem(message, request, caller, now)
        if problem is not None:
            record_in_transaction(
                transaction,
                caller,
                OperationName.REPLY.value,
                now,
                to_ref=None,
                message_id=request.id,
                parent_id=None,
                code=problem.code,
                detail=problem.detail,
            )
            return ReplyResult.rejected(problem.code, (problem.detail,))
        if message is None:
            raise AssertionError("a reply with no problem has a request")
        state, event = _RESULT[request.action]
        changed = change_state(
            transaction, message, state, event, caller, now, _fields(request, now)
        )
        return ReplyResult(
            outcome=ReplyOutcome.APPLIED,
            notice=QUOTED_DATA_NOTICE,
            rejection=None,
            request=RequestView.from_message(changed, now, RequestDirection.RECEIVED),
            problems=(),
        )


def _fields(request: ReplyRequest, now: datetime) -> StateFields:
    """What the action writes beyond the state (D4 table)."""
    match request.action:
        case ReplyAction.ACCEPT:
            return StateFields(accepted_at=now)
        case ReplyAction.DECLINE:
            return StateFields(reason=request.text)
        case ReplyAction.DONE:
            return StateFields(
                result=request.text,
                result_commit=request.commit,
                result_version=request.version,
            )


def _problem(
    message: Message | None, request: ReplyRequest, caller: str, now: datetime
) -> Refusal | None:
    """The D4 refusal for this reply, or ``None`` when it may be applied."""
    found = as_request(request.id, message)
    if isinstance(found, NotARequest):
        return Refusal(RejectCode.UNKNOWN_REQUEST, found.detail, record_under=caller)
    message = found
    if message.to_member != caller:
        return Refusal(
            RejectCode.NOT_ADDRESSEE,
            f"request {request.id!r} was not sent to this member",
            record_under=caller,
        )
    state = effective_state(message, now)
    if state in _ALLOWED_FROM[request.action]:
        return None
    if state is RequestState.ACCEPTED and request.action is ReplyAction.ACCEPT:
        if message.accepted_at is None:
            raise AssertionError(f"accepted request {request.id!r} has no accepted_at")
        return Refusal(
            RejectCode.ALREADY_ACCEPTED,
            f"request {request.id!r} was already accepted at "
            f"{encode_timestamp(message.accepted_at)}",
            record_under=caller,
        )
    if state is RequestState.OPEN:
        return Refusal(
            RejectCode.NOT_APPLICABLE,
            f"request {request.id!r} is open: accept it first, then mark it done",
            record_under=caller,
        )
    return Refusal(
        RejectCode.NOT_APPLICABLE,
        f"request {request.id!r} is already {state}",
        record_under=caller,
    )
