"""The session tick: one loop for presence and push (slice 263, D1, D3, D4).

One pass is the member lookup (D3), one ``session_tick`` step in a worker thread, the
reply handled on the event loop, and then a sleep of the reply's
``notify_poll_seconds`` that starts when the pass ends, so two ticks never overlap. The
worker thread opens its own steps (``deps.open_steps``) and closes them when the step
returns: a sqlite connection cannot cross threads, so a ``Steps`` never does either.

A reply updates ``PresenceState`` and, when the member's highest delivery number rose
since the last reply, sends one channel event built from the reply's entries. Mail
before a baseline is ``inbox``'s to report. Every operational failure skips the tick
and the loop goes on (D4); anything else is a bug and reaches the presence task's one
top-level handler.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

import anyio
import anyio.to_thread
from mcp.server.connection import Connection

from amoeba.mcp.after_runner import AfterRunner
from amoeba.mcp.channel_event import (
    CHANNEL_METHOD,
    META_COUNT,
    META_FIRST_SEQ,
    META_LAST_SEQ,
    channel_event,
)
from amoeba.mcp.inbox_resource import INBOX_URI, RESOURCE_UPDATED_METHOD
from amoeba.mcp.presence import (
    FailureLog,
    PresenceDeps,
    PresenceState,
    note_event_attempted,
)
from amoeba.wiring_presence import (
    ClientFileError,
    ConfigError,
    ContextForgeError,
    HereCaller,
    HereNotAProject,
    HubCertificateError,
    HubRefusedError,
    HubUnreachableError,
    LastReply,
    SessionIdentity,
    SessionTickReply,
    SessionTickRequest,
    StoreError,
    gather_here,
    machine_name,
    tick_session,
    way_of,
)

logger = logging.getLogger(__name__)

#: The wait between tries until a first reply has come: the only interval the client
#: holds, because a session must be able to start with the hub down (D1, D8).
TICK_SECONDS_BEFORE_FIRST_REPLY: Final = 5.0
#: How old "not a project" is before ``cf`` is asked again (D3).
CF_REASK_SECONDS: Final = 60.0
#: Every operational failure of a pass: the pass is skipped (D4).
TICK_ERRORS: Final = (
    ContextForgeError,
    ClientFileError,
    HubUnreachableError,
    HubCertificateError,
    HubRefusedError,
    StoreError,
    ConfigError,
)


@dataclass
class HereCache:
    """What the last ``cf`` answer was (D3): a project id is kept for the process, and
    "not a project" until it is ``CF_REASK_SECONDS`` old."""

    project: HereCaller | None = None
    not_a_project: HereNotAProject | None = None
    asked_at: datetime | None = None


@dataclass(frozen=True)
class TickOutcome:
    """What one pass's worker thread brings back."""

    reply: SessionTickReply
    way: str
    machine: str
    #: What the reply said about waiting work, for the after-step.
    last: LastReply


async def _here(
    cache: HereCache, directory: str, deps: PresenceDeps
) -> HereCaller | HereNotAProject:
    """The caller as ``cf`` gives it; a failure raises and skips the tick."""
    if cache.project is not None:
        return cache.project
    now = deps.clock()
    asked = cache.asked_at
    if (
        cache.not_a_project is not None
        and asked is not None
        and now - asked < timedelta(seconds=CF_REASK_SECONDS)
    ):
        return cache.not_a_project
    found = await anyio.to_thread.run_sync(
        gather_here, Path(directory), deps.cf_run, abandon_on_cancel=True
    )
    if isinstance(found, HereCaller):
        cache.project, cache.not_a_project = found, None
    else:
        cache.not_a_project, cache.asked_at = found, now
    return found


def _request(
    state: PresenceState,
    here: HereCaller | HereNotAProject,
    identity: SessionIdentity,
    way: str,
) -> SessionTickRequest:
    """The request for a pass that goes ``way``: no ``last_seen`` when the way is not
    the one the baseline was taken on (the two stores' numbers are unrelated, D1)."""
    return SessionTickRequest(
        here=here,
        session_id=state.session_id,
        client=identity.client,
        directory=identity.directory,
        last_seen=state.last_seen if way == state.way else None,
        push_confirmed=state.push_confirmed_at is not None,
    )


def _directory(state: PresenceState) -> str:
    if state.directory is None:
        raise ValueError("a tick needs the process's directory")
    return state.directory


async def _step(
    state: PresenceState,
    deps: PresenceDeps,
    here: HereCaller | HereNotAProject,
    client: str,
) -> TickOutcome:
    """The pass's step, in a worker thread that opens and closes its own steps."""

    identity = SessionIdentity(
        session_id=state.session_id,
        project_id=here.project_id if isinstance(here, HereCaller) else None,
        client=client,
        directory=_directory(state),
    )
    state.identity = identity

    def work() -> TickOutcome:
        last = LastReply()
        with deps.open_steps(last, identity) as steps:
            way = way_of(steps)
            reply = tick_session(steps, _request(state, here, identity, way))
        return TickOutcome(reply, way, machine_name(), last)

    # Abandoned at exit rather than waited for (D8): it finishes on its own.
    return await anyio.to_thread.run_sync(work, abandon_on_cancel=True)


def _rebases(state: PresenceState, outcome: TickOutcome) -> bool:
    """Whether this reply starts a new baseline, with no event: the first reply, a
    changed way or member, or a highest number below the last one seen (D1)."""
    reply = outcome.reply
    return (
        state.last_seen is None
        or outcome.way != state.way
        or reply.member_id != state.baseline_member
        or reply.high_seq < state.last_seen
    )


async def _announce(
    connection: Connection,
    state: PresenceState,
    deps: PresenceDeps,
    reply: SessionTickReply,
) -> None:
    event = channel_event(reply.entries, count=reply.count, last_seq=reply.high_seq)
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


async def _handle_reply(
    connection: Connection,
    state: PresenceState,
    deps: PresenceDeps,
    outcome: TickOutcome,
    client: str,
) -> None:
    """Take the reply into ``state`` and send the event a rise calls for."""
    reply = outcome.reply
    rebase = _rebases(state, outcome)
    if reply.member_id is not None and reply.member_id != state.member_id:
        logger.info(
            "presence for %s: protocol %s, client %s, machine %s",
            reply.member_id,
            connection.protocol_version,
            client,
            outcome.machine,
        )
    if reply.member_id is None and reply.reason != state.off_reason:
        # Once per change of reason, not per tick: a session in a non-member directory
        # ticks for as long as it lives.
        logger.info(
            "no presence: %s is not a member (%s)", state.directory, reply.reason
        )
    state.member_id, state.member_name = reply.member_id, reply.member_name
    state.off_reason = reply.reason
    state.told_member = state.told_member or reply.member_id is not None
    state.as_of_seq, state.poll_seconds = reply.as_of_seq, reply.notify_poll_seconds
    state.last_error = None
    state.way, state.baseline_member = outcome.way, reply.member_id
    state.last_seen = None if reply.member_id is None else reply.high_seq
    if not rebase and reply.entries:
        await _announce(connection, state, deps, reply)


def _interval(state: PresenceState) -> float:
    seconds = state.poll_seconds
    return TICK_SECONDS_BEFORE_FIRST_REPLY if seconds is None else seconds


async def run_ticks(
    connection: Connection,
    state: PresenceState,
    deps: PresenceDeps,
    client: str,
    runner: AfterRunner,
) -> None:
    """Tick until cancelled. ``state.resolved`` is set when the first pass ends.

    Raises:
        Exception: Anything that is not an operational failure (D4), or what
            ``Connection.notify`` raises beyond a closed stream.
    """
    failures = FailureLog("tick")
    cache = HereCache()
    while True:
        try:
            here = await _here(cache, _directory(state), deps)
            outcome = await _step(state, deps, here, client)
        except TICK_ERRORS as error:
            # Skipped, not ended (D4): the next pass is the retry, and the first one
            # that succeeds writes the row again and finds the mail since.
            state.last_error = f"{type(error).__name__}: {error}"
            failures.failed(error)
        else:
            failures.recovered()
            await _handle_reply(connection, state, deps, outcome, client)
            runner.start(outcome.last)
        finally:
            state.resolved.set()
        await anyio.sleep(_interval(state))
