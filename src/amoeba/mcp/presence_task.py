"""The presence task beside the serve loop: its one top-level handler and clean exit
(slice 241, D2, D3, D6).

The task shares a task group with ``serve_connection``, so an exception escaping it
would cancel the loop and end every tool. Its one handler catches ``Exception`` (not
``BaseException``: cancellation passes), logs it with its traceback and ends presence;
the server keeps serving its tools. However the task ends, a shielded, bounded delete
removes the session row.
"""

from __future__ import annotations

import logging
from typing import Final

import anyio
import anyio.to_thread
from mcp.server.connection import Connection

from amoeba.mcp.inbox_watcher import watch_inbox
from amoeba.mcp.presence import (
    PresenceDeps,
    PresenceState,
    client_name,
    heartbeat_loop,
    resolve_presence,
)
from amoeba.wiring_presence import BUSY_TIMEOUT_SECONDS, StoreError, end_session

logger = logging.getLogger(__name__)

#: The bound on the exit delete: two busy waits (D6).
EXIT_DELETE_SECONDS: Final = BUSY_TIMEOUT_SECONDS * 2


def _client_info_name(connection: Connection) -> str | None:
    params = connection.client_params
    return None if params is None else params.client_info.name


async def _serve_presence(
    connection: Connection, state: PresenceState, deps: PresenceDeps
) -> None:
    await resolve_presence(state, deps)
    if state.member_id is None:
        return
    await connection.initialized.wait()
    client = client_name(_client_info_name(connection))
    logger.info(
        "presence for %s: protocol %s, client %s",
        state.member_id,
        connection.protocol_version,
        client,
    )
    async with anyio.create_task_group() as group:
        group.start_soon(heartbeat_loop, state, deps, client)
        group.start_soon(watch_inbox, connection, state, deps)


async def _delete_row(state: PresenceState, deps: PresenceDeps) -> None:
    """Remove the row, shielded and bounded; a failure leaves it to go stale."""
    with (
        anyio.CancelScope(shield=True),
        anyio.move_on_after(EXIT_DELETE_SECONDS) as bound,
    ):
        try:
            await anyio.to_thread.run_sync(
                end_session, deps.open_store, state.session_id, abandon_on_cancel=True
            )
        except StoreError:
            # The row stops counting after session_stale_seconds and the next
            # heartbeat of any server prunes it (D6), so a failed delete costs
            # nothing but that wait.
            logger.exception("session row not deleted; it goes stale")
    if bound.cancelled_caught:
        logger.warning(
            "session row not deleted within %ss; it goes stale", EXIT_DELETE_SECONDS
        )


async def run_presence(
    connection: Connection, state: PresenceState, deps: PresenceDeps
) -> None:
    """Resolve the member and, for a member, keep its session row until the end."""
    try:
        await _serve_presence(connection, state, deps)
    except Exception:
        # The process boundary of presence (D2): anything it raises ends presence,
        # never the loop, and the tools report their own errors.
        logger.exception("presence stopped; the tools keep serving")
    finally:
        if state.member_id is not None:
            await _delete_row(state, deps)
