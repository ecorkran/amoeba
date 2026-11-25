"""``session_tick`` and ``session_end``'s models (263 D2).

Neither request holds a time: the hub stamps every session time with its own clock
(D5). A reply holds numbers, closed words and a member id, never message text.
"""

from __future__ import annotations

from typing import Final

from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.steps.model_base import Step, StepModel
from amoeba.store.vocabulary import DeliveryEvent, MessageKind


class SessionTickRequest(StepModel):
    """One tick as the client sends it."""

    here: HereCaller | HereNotAProject
    session_id: str
    client: str
    directory: str
    #: The highest delivery number the session has seen, or ``None`` for a baseline.
    last_seen: int | None
    push_confirmed: bool


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
