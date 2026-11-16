"""The push loop: tell the client when its member's deliveries rise (slice 241, D2,
D4, D5).

Every ``notify_poll_seconds`` a worker thread opens the store and makes one indexed
read; no connection is held between ticks (an open and read measured 0.4 ms, against
the example config's 5 s interval). A rise opens it again to read the new rows,
sends one channel event for all of them, records the attempt for push confirmation,
and sends a resource update to a client that subscribed. Nothing is written and no
marker is kept, so another reader never misses mail. The watcher sends nothing until
it has a baseline, so mail already waiting is ``inbox``'s to report.
"""

from __future__ import annotations

import logging

import anyio
import anyio.to_thread
from mcp.server.connection import Connection

from amoeba.mcp.channel_event import (
    CHANNEL_METHOD,
    META_COUNT,
    META_FIRST_SEQ,
    META_LAST_SEQ,
    channel_event,
)
from amoeba.mcp.inbox_resource import INBOX_URI, RESOURCE_UPDATED_METHOD
from amoeba.mcp.presence import (
    BusyWarning,
    PresenceDeps,
    PresenceState,
    note_event_attempted,
)
from amoeba.wiring_presence import (
    PushRow,
    StoreBusyError,
    read_high_seq,
    read_push_rows,
)

logger = logging.getLogger(__name__)


async def _baseline(member_id: str, deps: PresenceDeps, busy: BusyWarning) -> int:
    """The member's high seq, retried each tick until a read succeeds."""
    while True:
        try:
            seq = await anyio.to_thread.run_sync(
                read_high_seq, deps.open_store, member_id
            )
        except StoreBusyError as error:
            # Push is a hint and polling is the floor: retry at the next tick.
            busy.failed(error)
            await anyio.sleep(deps.timing.notify_poll_seconds)
            continue
        busy.cleared()
        return seq


async def _new_rows(
    member_id: str, last_seen: int, deps: PresenceDeps
) -> tuple[int, tuple[PushRow, ...]]:
    """The new last-seen seq, and the rows above ``last_seen`` when the high rose.

    The floor is the last row read, not the high: a delivery committed between the
    two reads is in ``rows``, and must not be read again next tick.
    """
    high = await anyio.to_thread.run_sync(read_high_seq, deps.open_store, member_id)
    if high <= last_seen:
        return last_seen, ()
    rows = await anyio.to_thread.run_sync(
        read_push_rows, deps.open_store, member_id, last_seen
    )
    return (rows[-1].seq if rows else high), rows


async def _announce(
    connection: Connection,
    state: PresenceState,
    deps: PresenceDeps,
    rows: tuple[PushRow, ...],
) -> None:
    event = channel_event(rows)
    await connection.notify(CHANNEL_METHOD, dict(event))
    note_event_attempted(state, deps.clock())
    if state.subscribed:
        await connection.notify(RESOURCE_UPDATED_METHOD, {"uri": INBOX_URI})
    meta = event["meta"]
    logger.info(
        "channel event attempted: first_seq=%s last_seq=%s count=%s",
        meta[META_FIRST_SEQ],
        meta[META_LAST_SEQ],
        meta[META_COUNT],
    )


async def watch_inbox(
    connection: Connection, state: PresenceState, deps: PresenceDeps
) -> None:
    """Push for the resolved member until cancelled.

    Raises:
        StoreError: Any store failure but a busy store.
        Exception: Whatever ``Connection.notify`` raises beyond a closed stream.
    """
    member_id = state.member_id
    if member_id is None:
        raise ValueError("the watcher runs only for a resolved member")
    busy = BusyWarning("push check")
    last_seen = await _baseline(member_id, deps, busy)
    while True:
        await anyio.sleep(deps.timing.notify_poll_seconds)
        try:
            last_seen, rows = await _new_rows(member_id, last_seen, deps)
        except StoreBusyError as error:
            # As the baseline: this tick is skipped, the next one reads again.
            busy.failed(error)
            continue
        busy.cleared()
        if rows:
            await _announce(connection, state, deps, rows)
