"""The presence task beside the serve loop: the tick, the after-step runner, its one
top-level handler and the exit (slice 241, D2, D3; slice 263, D1, D7, D8).

The task shares a task group with ``serve_connection``, so an exception escaping it
would cancel the loop and end every tool. Its one handler catches ``Exception`` (not
``BaseException``: cancellation passes), logs it with its traceback and ends presence;
the server keeps serving its tools. However the task ends, a session that was ever
told it has a member makes one shielded, bounded ``session_end`` attempt.
"""

from __future__ import annotations

import logging
from pathlib import Path

import anyio
import anyio.to_thread
from mcp.server.connection import Connection

from amoeba.mcp.after_runner import AfterRunner
from amoeba.mcp.presence import PresenceDeps, PresenceState, client_name
from amoeba.mcp.tick import run_ticks
from amoeba.wire.times import TICK_BOUND_SECONDS
from amoeba.wiring_presence import (
    ClientFileError,
    ConfigError,
    HubRefusedError,
    HubUnreachableError,
    LastReply,
    StoreError,
    end_session,
)

logger = logging.getLogger(__name__)


def _client_info_name(connection: Connection) -> str | None:
    params = connection.client_params
    return None if params is None else params.client_info.name


async def _serve_presence(
    connection: Connection, state: PresenceState, deps: PresenceDeps
) -> None:
    state.directory = str(Path.cwd())
    await connection.initialized.wait()
    client = client_name(_client_info_name(connection))
    async with anyio.create_task_group() as group:
        runner = AfterRunner(deps, lambda work: group.start_soon(work))
        group.start_soon(run_ticks, connection, state, deps, client, runner)


def _end_in_thread(state: PresenceState, deps: PresenceDeps) -> None:
    with deps.open_steps(LastReply()) as steps:
        end_session(steps, state.session_id)


async def _end_session(state: PresenceState, deps: PresenceDeps) -> None:
    """One ``session_end`` attempt, shielded and bounded by ``TICK_BOUND_SECONDS``.

    A failure that is an absence of a reply leaves the row to go stale; any other
    error is a bug and is not caught here.
    """
    with (
        anyio.CancelScope(shield=True),
        anyio.move_on_after(TICK_BOUND_SECONDS) as bound,
    ):
        try:
            await anyio.to_thread.run_sync(
                _end_in_thread, state, deps, abandon_on_cancel=True
            )
        except (
            HubUnreachableError,
            HubRefusedError,
            ClientFileError,
            StoreError,
            ConfigError,
        ) as error:
            # Swallowing is correct: with no reply the row stops counting after
            # session_stale_seconds and the next refresh by any session deletes it
            # (D4, D8), so a failed end costs nothing but that wait.
            logger.warning("session end failed: %s: %s", type(error).__name__, error)
    if bound.cancelled_caught:
        logger.warning(
            "session end not finished within %ss; the row goes stale",
            TICK_BOUND_SECONDS,
        )


async def run_presence(
    connection: Connection, state: PresenceState, deps: PresenceDeps
) -> None:
    """Tick for the session's member until the end, then end the session's row."""
    try:
        try:
            await _serve_presence(connection, state, deps)
        finally:
            state.resolved.set()
            if state.told_member:
                await _end_session(state, deps)
    except Exception:
        # The process boundary of presence (D2): anything it raises ends presence,
        # never the loop, and the tools report their own errors.
        logger.exception("presence stopped; the tools keep serving")
