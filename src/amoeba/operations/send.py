"""``send``: ask another member for work, or tell it something with a note (slice 240,
D2, D3, D9; slice 243, D1).

The sender and the recipient are resolved, and the document validated, before any
store lock, so no ``cf`` call runs under one. A refusal found once the sender is known
writes a ``message_rejections`` row and returns ``rejected``; ``not_a_member`` has no
member to show a row under and writes none.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from pydantic import ValidationError

from amoeba.config.user_config import UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.message_document import declared_text
from amoeba.operations.message_member import (
    Recipient,
    Refusal,
    caller_of,
    recipient_of,
)
from amoeba.operations.message_models import SendRequest
from amoeba.operations.message_rejection import record_declared
from amoeba.operations.message_results import SendResult
from amoeba.operations.names import OperationName
from amoeba.operations.reject_codes import RejectCode, validation_problems
from amoeba.operations.send_note import write_note
from amoeba.operations.send_write import write_send
from amoeba.operations.wake import wake_for_sent_request
from amoeba.store.store import Store
from amoeba.store.vocabulary import MessageKind

__all__ = ["SendResult", "send"]


def send(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    here: HereCaller | HereNotAProject,
    deps: Deps,
) -> SendResult:
    """Send the request in ``document`` from the member whose checkout ``here`` is.

    Raises:
        StoreError: The store cannot be used.
    """
    now = deps.clock()
    caller = caller_of(store, here, declared_text(document, "member"))
    if isinstance(caller, Refusal):
        return _refuse(store, caller, document, now)
    try:
        request = SendRequest.model_validate(document)
    except ValidationError as error:
        problems = validation_problems(error)
        malformed = Refusal(RejectCode.MALFORMED, "; ".join(problems), caller.member_id)
        return _refuse(store, malformed, document, now, problems)
    recipient: Recipient | Refusal | None = (
        None if request.to is None else recipient_of(store, request.to)
    )
    if isinstance(recipient, Refusal):
        return _refuse(
            store, replace(recipient, record_under=caller.member_id), document, now
        )
    if request.kind is MessageKind.NOTE:
        return write_note(
            store,
            config,
            sender=caller.member_id,
            recipient=None if recipient is None else recipient.member_id,
            request=request,
            now=now,
        )
    if recipient is None:
        raise AssertionError("a request names its recipient; the model checked")
    result = write_send(
        store,
        config,
        sender=caller.member_id,
        recipient=recipient.member_id,
        request=request,
        now=now,
    )
    return wake_for_sent_request(store, config, deps, recipient, result)


def _refuse(
    store: Store,
    refusal: Refusal,
    document: object,
    now: datetime,
    problems: tuple[str, ...] | None = None,
) -> SendResult:
    """Record the refusal under its member, when it has one, and return it."""
    record_declared(store, refusal, OperationName.SEND.value, document, now)
    return SendResult.rejected(
        refusal.code, (refusal.detail,) if problems is None else problems
    )
