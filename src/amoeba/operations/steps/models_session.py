"""``session_tick`` and ``session_end``'s models (263 D2).

Neither request holds a time: the hub stamps every session time with its own clock
(D5). A reply holds numbers, closed words and a member id, never message text.
"""

from __future__ import annotations

from typing import Final

from pydantic import field_validator

from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.steps.model_base import Step, StepModel
from amoeba.store.vocabulary import DeliveryEvent, MessageKind
from amoeba.wire.protocol import CLIENT_NAME_PATTERN, is_session_directory


class SessionTickRequest(StepModel):
    """One tick as the client sends it."""

    here: HereCaller | HereNotAProject
    session_id: str
    client: str
    directory: str
    #: The version of the program that sends the tick, stored as the session's
    #: ``client_version`` (the hub's own version is not the client's over the door).
    client_version: str
    #: The highest delivery number the session has seen, or ``None`` for a baseline.
    last_seen: int | None
    push_confirmed: bool

    @field_validator("client")
    @classmethod
    def _client_has_the_shape_of_a_name(cls, value: str) -> str:
        if CLIENT_NAME_PATTERN.fullmatch(value) is None:
            raise ValueError("client is not a client name the list may show")
        return value

    @field_validator("directory")
    @classmethod
    def _directory_is_storable(cls, value: str) -> str:
        if not is_session_directory(value):
            raise ValueError("directory is empty, too long or holds control characters")
        return value


class TickEntry(StepModel):
    """A delivery as the channel event names it: no message text."""

    seq: int
    event: DeliveryEvent
    kind: MessageKind
    #: A member id.
    counterparty: str


class SessionTickReply(StepModel):
    """The session's member (or why it has none) and what is new for it."""

    #: ``None`` with a ``reason`` when the caller is no member.
    member_id: str | None
    member_name: str | None
    reason: str | None
    high_seq: int
    #: The first entry's number, ``None`` when there is none.
    first_seq: int | None
    #: How many deliveries are above ``last_seen`` in all; ``entries`` holds at most
    #: ``CHANNEL_EVENT_MAX_ENTRIES`` of them.
    count: int
    entries: tuple[TickEntry, ...]
    as_of_seq: int
    notify_poll_seconds: float


class SessionEndRequest(StepModel):
    session_id: str


class SessionEndReply(StepModel):
    """No fields."""


#: A write that is safe to run twice keeps no result (D2); the tick reads three
#: timing keys of the config.
SESSION_TICK: Final = Step(
    "session_tick",
    SessionTickRequest,
    SessionTickReply,
    writes=True,
    keeps_result=False,
    needs_config=True,
)
SESSION_END: Final = Step(
    "session_end",
    SessionEndRequest,
    SessionEndReply,
    writes=True,
    keeps_result=False,
    needs_config=False,
)
