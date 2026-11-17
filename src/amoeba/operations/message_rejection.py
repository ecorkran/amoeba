"""Recording a refusal found before the write transaction (slice 240, D9).

``member_mismatch``, a malformed document and an unknown recipient are found while
resolving, before any lock is taken. Each writes its ``message_rejections`` row in its
own short transaction. A refusal found inside an operation's write transaction writes
its row there instead.
"""

from __future__ import annotations

from datetime import datetime

from amoeba.operations.message_document import declared_recipient, declared_text
from amoeba.operations.message_member import Refusal
from amoeba.operations.message_models import (
    MAX_RECORDED_LENGTH,
    MAX_REJECTIONS_PER_MEMBER,
)
from amoeba.operations.reject_codes import RejectCode
from amoeba.store.message_rejections import record_rejection, trim_rejections
from amoeba.store.store import Store, Transaction

ELLIPSIS = "…"


def _recorded(text: str | None) -> str | None:
    """``text`` as a row keeps it: at most ``MAX_RECORDED_LENGTH`` characters, ending in
    ``…`` when it was cut."""
    if text is None or len(text) <= MAX_RECORDED_LENGTH:
        return text
    return text[: MAX_RECORDED_LENGTH - len(ELLIPSIS)] + ELLIPSIS


def record_in_transaction(
    transaction: Transaction,
    member_id: str,
    operation: str,
    now: datetime,
    *,
    to_ref: str | None,
    message_id: str | None,
    parent_id: str | None,
    code: RejectCode,
    detail: str,
) -> None:
    """One row for the caller ``member_id`` in the transaction that found the
    problem, so it commits with whatever that transaction returns.

    The text the caller gave is bounded (``MAX_RECORDED_LENGTH``), and the member keeps
    only its newest ``MAX_REJECTIONS_PER_MEMBER`` rows.
    """
    record_rejection(
        transaction,
        member_id,
        operation,
        _recorded(to_ref),
        _recorded(message_id),
        _recorded(parent_id),
        code.value,
        _recorded(detail) or "",
        now,
    )
    trim_rejections(transaction, member_id, MAX_REJECTIONS_PER_MEMBER)


def record_refusal(
    store: Store,
    member_id: str,
    operation: str,
    now: datetime,
    *,
    to_ref: str | None,
    message_id: str | None,
    parent_id: str | None,
    code: RejectCode,
    detail: str,
) -> None:
    """One row for the caller ``member_id``, committed on its own.

    Raises:
        StoreError: The store cannot be used.
    """
    with store.write() as transaction:
        record_in_transaction(
            transaction,
            member_id,
            operation,
            now,
            to_ref=to_ref,
            message_id=message_id,
            parent_id=parent_id,
            code=code,
            detail=detail,
        )


def record_declared(
    store: Store, refusal: Refusal, operation: str, document: object, now: datetime
) -> None:
    """Record ``refusal`` for the member it names, with the ``id``, ``to`` and
    ``parent`` the document gave (leniently read: a malformed document is recorded
    too). Writes nothing when the refusal has no member to show a row under.

    Raises:
        StoreError: The store cannot be used.
    """
    if refusal.record_under is None:
        return
    record_refusal(
        store,
        refusal.record_under,
        operation,
        now,
        to_ref=declared_recipient(document),
        message_id=declared_text(document, "id"),
        parent_id=declared_text(document, "parent"),
        code=refusal.code,
        detail=refusal.detail,
    )
