"""The Claude Code channel event that says mail arrived (slice 241, D4).

A pure function of push rows, with no I/O. The event is text the model reads as a
user turn, so it is built only from closed vocabularies (``MessageKind``,
``DeliveryEvent``), sequence numbers and Context Forge member ids. No subject, body,
result, reason or request id is a parameter here: message text reaches the agent only
through ``inbox``, under its notice.

The instruction points the agent at its own cursor, never a number from the event, so
an agent that ignored an earlier event does not skip it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, TypedDict

from amoeba.operations.names import OperationName
from amoeba.wire.protocol import CHANNEL_EVENT_MAX_ENTRIES
from amoeba.wiring_presence import DeliveryEvent, PushRow

#: The notification method Claude Code listens on (channels reference, 20261116).
CHANNEL_METHOD: Final = "notifications/claude/channel"
#: The ``experimental`` capability key that registers the listener.
CHANNEL_CAPABILITY: Final = "claude/channel"
#: ``meta`` keys: identifiers only, or Claude Code drops them silently.
META_FIRST_SEQ: Final = "first_seq"
META_LAST_SEQ: Final = "last_seq"
META_COUNT: Final = "count"


class ChannelEventParams(TypedDict):
    """The notification's params: ``content`` becomes the ``<channel>`` tag body."""

    content: str
    meta: dict[str, str]


def _entry(row: PushRow) -> str:
    """``<kind>, <event> from|with <member id>``.

    A ``sent`` delivery is always the counterparty's new message, so ``from``; every
    other event concerns a request between the two, so ``with``.
    """
    preposition = "from" if row.event is DeliveryEvent.SENT else "with"
    return f"{row.kind.value}, {row.event.value} {preposition} {row.counterparty}"


def _entries(rows: Sequence[PushRow]) -> str:
    listed = "; ".join(_entry(row) for row in rows[:CHANNEL_EVENT_MAX_ENTRIES])
    hidden = len(rows) - CHANNEL_EVENT_MAX_ENTRIES
    return f"{listed}; and {hidden} more" if hidden > 0 else listed


def channel_event(rows: Sequence[PushRow]) -> ChannelEventParams:
    """The event for ``rows``, which are in ``seq`` order and not empty."""
    if not rows:
        raise ValueError("a channel event needs at least one delivery")
    first, last, count = rows[0].seq, rows[-1].seq, len(rows)
    noun = "delivery" if count == 1 else "deliveries"
    content = (
        f"Amoeba: {count} new {noun} for this repo (seq {first}-{last}): "
        f"{_entries(rows)}. Call the {OperationName.INBOX.value} tool. Pass "
        "since=<as_of_seq from your last inbox call>, or omit since if you have none."
    )
    meta = {
        META_FIRST_SEQ: str(first),
        META_LAST_SEQ: str(last),
        META_COUNT: str(count),
    }
    return ChannelEventParams(content=content, meta=meta)
