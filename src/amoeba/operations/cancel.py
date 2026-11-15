"""``cancel``: end a request that is open or accepted (slice 240, D3, D4, D5, D9).

Nothing about the caller is checked: the sender's agent or any agent acting for the PM
may cancel, if it names the request id. The caller is resolved only to leave it out of
the deliveries, and a directory in no member is not an error: the actor is then unknown
and both parties are told. A refusal is recorded only when the caller is known.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from amoeba.config.user_config import UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.message_document import declared_text
from amoeba.operations.message_member import (
    Caller,
    Refusal,
    UnknownActor,
    resolve_actor,
)
from amoeba.operations.message_models import CancelOutcome, CancelRequest
from amoeba.operations.message_rejection import (
    record_declared,
    record_in_transaction,
)
from amoeba.operations.message_results import (
    CancelResult,
    RequestDirection,
    RequestView,
)
from amoeba.operations.names import OperationName
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.operations.reject_codes import RejectCode, validation_problems
from amoeba.store.message_sweep import sweep
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import effective_state, get_message
from amoeba.store.models import Message
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, RequestState

__all__ = ["CancelResult", "cancel"]

#: The states a request can be cancelled from.
_CANCELLABLE: Final = frozenset({RequestState.OPEN, RequestState.ACCEPTED})


def cancel(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    directory: Path,
    deps: Deps,
) -> CancelResult:
    """Cancel the request named in ``document``.

    Raises:
        ContextForgeError: ``cf`` failed or timed out; nothing was written.
        StoreError: The store cannot be used.
    """
    now = deps.clock()
    actor = resolve_actor(
        store, directory, declared_text(document, "member"), deps.cf_run
    )
    if isinstance(actor, Refusal):
        record_declared(store, actor, OperationName.CANCEL.value, document, now)
        return CancelResult.rejected(actor.code, (actor.detail,))
    try:
        request = CancelRequest.model_validate(document)
    except ValidationError as error:
        problems = validation_problems(error)
        if isinstance(actor, Caller):
            malformed = Refusal(
                RejectCode.MALFORMED, "; ".join(problems), actor.member_id
            )
            record_declared(store, malformed, OperationName.CANCEL.value, document, now)
        return CancelResult.rejected(RejectCode.MALFORMED, problems)
    return _apply(store, config, request, actor, now)


def _apply(
    store: Store,
    config: UserConfig,
    request: CancelRequest,
    actor: Caller | UnknownActor,
    now: datetime,
) -> CancelResult:
    actor_id = actor.member_id if isinstance(actor, Caller) else None
    with store.write() as transaction:
        sweep(transaction, now, config.prune_after_days)
        message = get_message(transaction, request.id)
        problem = _problem(message, request, actor_id, now)
        if problem is not None:
            if actor_id is not None:
                record_in_transaction(
                    transaction,
                    actor_id,
                    OperationName.CANCEL.value,
                    now,
                    to_ref=None,
                    message_id=request.id,
                    parent_id=None,
                    code=problem.code,
                    detail=problem.detail,
                )
            return CancelResult.rejected(problem.code, (problem.detail,))
        if message is None:
            raise AssertionError("a cancel with no problem has a request")
        changed = change_state(
            transaction,
            message,
            RequestState.CANCELLED,
            DeliveryEvent.CANCELLED,
            actor_id,
            now,
            StateFields(reason=request.reason),
        )
        return CancelResult(
            outcome=CancelOutcome.CANCELLED,
            notice=QUOTED_DATA_NOTICE,
            rejection=None,
            request=RequestView.from_message(
                changed, now, _direction(changed, actor_id)
            ),
            problems=(),
        )


def _direction(message: Message, actor_id: str | None) -> RequestDirection | None:
    """The request relative to the actor; ``None`` when it is neither party."""
    if actor_id == message.from_member:
        return RequestDirection.SENT
    if actor_id == message.to_member:
        return RequestDirection.RECEIVED
    return None


def _problem(
    message: Message | None,
    request: CancelRequest,
    actor_id: str | None,
    now: datetime,
) -> Refusal | None:
    """Why this cancel cannot be applied, or ``None`` when it may be."""
    if message is None:
        return Refusal(
            RejectCode.UNKNOWN_REQUEST,
            f"no request has the id {request.id!r}",
            record_under=actor_id,
        )
    state = effective_state(message, now)
    if state is None:
        raise ValueError(f"{request.id!r} is not a request; it has no state")
    if state in _CANCELLABLE:
        return None
    return Refusal(
        RejectCode.NOT_APPLICABLE,
        f"request {request.id!r} is already {state.value}",
        record_under=actor_id,
    )
