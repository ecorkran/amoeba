"""The views and results of ``send``, ``inbox``, ``reply`` and ``cancel`` (slice 240,
D7, D11).

The views are built from the store's frozen rows (``RequestView.from_message``), never
the other way. Times are datetimes, as in the status models (JSON gives them as UTC
ISO text). No operation logic is here.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from amoeba.operations.message_models import (
    CancelOutcome,
    InboxOutcome,
    ReplyOutcome,
    SendOutcome,
)
from amoeba.operations.quoted_data import QUOTED_DATA_NOTICE
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.set_up_models import FrozenModel
from amoeba.store.messages import effective_state
from amoeba.store.models import Delivery, Message
from amoeba.store.vocabulary import DeliveryEvent, MessageKind, RequestState


class RequestDirection(StrEnum):
    """A request relative to the member reading it."""

    SENT = "sent"
    RECEIVED = "received"


class RequestView(FrozenModel):
    """A request as a member sees it (D7). Both members are ids: no message operation
    looks names up (``list`` and ``status`` show names)."""

    id: str
    #: Null when the caller is neither party (a ``cancel`` from a session in no
    #: member).
    direction: RequestDirection | None
    from_member: str
    to_member: str
    parent_id: str | None
    depth: int
    subject: str
    body: str
    #: The effective state: an open request past its expiry reads ``expired``.
    state: RequestState
    result: str | None
    result_commit: str | None
    result_version: str | None
    reason: str | None
    created_at: datetime
    accepted_at: datetime | None
    state_changed_at: datetime
    expires_at: datetime

    @classmethod
    def from_message(
        cls, message: Message, now: datetime, direction: RequestDirection | None
    ) -> RequestView:
        """The view of a request row at ``now``.

        Raises:
            ValueError: The row is not a request (240 writes none other).
            StoreRowError: The row is a note.
        """
        state = effective_state(message, now)
        if message.to_member is None or message.expires_at is None:
            raise ValueError(f"message {message.message_id!r} is not a request")
        return cls(
            id=message.message_id,
            direction=direction,
            from_member=message.from_member,
            to_member=message.to_member,
            parent_id=message.parent_id,
            depth=message.depth,
            subject=message.subject,
            body=message.body,
            state=state,
            result=message.result,
            result_commit=message.result_commit,
            result_version=message.result_version,
            reason=message.reason,
            created_at=message.created_at,
            accepted_at=message.accepted_at,
            state_changed_at=message.state_changed_at,
            expires_at=message.expires_at,
        )


class NoteView(FrozenModel):
    """A note as a member sees it (243 D1): information, with no state. Members and the
    program are ids."""

    id: str
    from_member: str
    #: Null for a program note.
    to_member: str | None
    #: Null for a direct note.
    to_program: str | None
    subject: str
    body: str
    created_at: datetime

    @classmethod
    def from_message(cls, message: Message) -> NoteView:
        """The view of a note row.

        Raises:
            ValueError: The row is not a note.
        """
        if message.kind is not MessageKind.NOTE:
            raise ValueError(f"message {message.message_id!r} is not a note")
        return cls(
            id=message.message_id,
            from_member=message.from_member,
            to_member=message.to_member,
            to_program=message.to_program,
            subject=message.subject,
            body=message.body,
            created_at=message.created_at,
        )


class DeliveryView(FrozenModel):
    """One thing a member should learn about a request; ``seq`` orders them."""

    seq: int
    message_id: str
    event: DeliveryEvent
    created_at: datetime

    @classmethod
    def from_delivery(cls, delivery: Delivery) -> DeliveryView:
        return cls(
            seq=delivery.seq,
            message_id=delivery.message_id,
            event=delivery.event,
            created_at=delivery.created_at,
        )


class SendResult(FrozenModel):
    """What ``send`` returns."""

    outcome: SendOutcome
    #: Says the text in requests is other agents' data (D11).
    notice: str
    #: Null unless rejected.
    rejection: RejectCode | None
    #: The stored request; null on rejection and for a note.
    request: RequestView | None
    #: The stored note; null on rejection and for a request.
    note: NoteView | None
    #: One line per problem when rejected; empty otherwise.
    problems: tuple[str, ...]
    #: Why the wake step of a stored request failed (a store error); the request is
    #: written regardless. Null when nothing went wrong (244 D2).
    wake_problem: str | None = None

    @classmethod
    def rejected(cls, code: RejectCode, problems: tuple[str, ...]) -> SendResult:
        return cls(
            outcome=SendOutcome.REJECTED,
            notice=QUOTED_DATA_NOTICE,
            rejection=code,
            request=None,
            note=None,
            problems=problems,
        )


class InboxResult(FrozenModel):
    """What ``inbox`` returns."""

    outcome: InboxOutcome
    notice: str
    rejection: RejectCode | None
    #: The caller's project id; null when rejected.
    member: str | None
    #: The ``since`` of the call, as given.
    since: int | None
    #: The highest delivery number ever assigned; pass it as the next ``since``.
    as_of_seq: int | None
    requests: tuple[RequestView, ...]
    #: The notes the member has a delivery for (243 D4); empty when none.
    notes: tuple[NoteView, ...]
    deliveries: tuple[DeliveryView, ...]
    problems: tuple[str, ...]

    @classmethod
    def rejected(
        cls, code: RejectCode, problems: tuple[str, ...], *, since: int | None
    ) -> InboxResult:
        return cls(
            outcome=InboxOutcome.REJECTED,
            notice=QUOTED_DATA_NOTICE,
            rejection=code,
            member=None,
            since=since,
            as_of_seq=None,
            requests=(),
            notes=(),
            deliveries=(),
            problems=problems,
        )


class ReplyResult(FrozenModel):
    """What ``reply`` returns."""

    outcome: ReplyOutcome
    notice: str
    rejection: RejectCode | None
    #: The request after the call; null on rejection.
    request: RequestView | None
    problems: tuple[str, ...]

    @classmethod
    def rejected(cls, code: RejectCode, problems: tuple[str, ...]) -> ReplyResult:
        return cls(
            outcome=ReplyOutcome.REJECTED,
            notice=QUOTED_DATA_NOTICE,
            rejection=code,
            request=None,
            problems=problems,
        )


class CancelResult(FrozenModel):
    """What ``cancel`` returns."""

    outcome: CancelOutcome
    notice: str
    rejection: RejectCode | None
    request: RequestView | None
    problems: tuple[str, ...]

    @classmethod
    def rejected(cls, code: RejectCode, problems: tuple[str, ...]) -> CancelResult:
        return cls(
            outcome=CancelOutcome.REJECTED,
            notice=QUOTED_DATA_NOTICE,
            rejection=code,
            request=None,
            problems=problems,
        )
