"""Presence: which member this server is, its session row and push confirmation
(slice 241, D2, D3, D6).

Only event-loop tasks touch ``PresenceState``. Every store and ``cf`` call runs in a
worker thread that opens its own store through the injected opener, so the loop only
sleeps, sends and keeps books.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Final
from uuid import uuid4

import anyio
import anyio.to_thread

from amoeba.wiring_presence import (
    CfRun,
    Session,
    StoreBusyError,
    StoreOpener,
    beat_session,
    lookup_member,
)

logger = logging.getLogger(__name__)

#: How long after an attempted channel event an ``inbox`` call still answers it: a
#: queued event waits for the agent's current turn to end (D6).
PUSH_ANSWER_SECONDS: Final = 300
#: A ``clientInfo.name`` shown by ``list``; anything else is stored as the placeholder.
CLIENT_NAME_PATTERN: Final = re.compile(r"[A-Za-z0-9._ -]{1,64}")
UNRECOGNIZED_CLIENT: Final = "unrecognized"


@dataclass(frozen=True)
class SessionTiming:
    """The three config keys (D7)."""

    notify_poll_seconds: float
    session_heartbeat_seconds: float
    session_stale_seconds: float


@dataclass(frozen=True)
class PresenceDeps:
    """What presence needs from outside; a test substitutes each."""

    open_store: StoreOpener
    cf_run: CfRun
    clock: Callable[[], datetime]
    timing: SessionTiming


@dataclass
class PresenceState:
    """The server's presence: pending, a member, or off with a reason.

    ``resolved`` is set once resolution ends, however it ends, so pending always ends.
    Read by the resource handlers, written by the presence task and ``call_tool``;
    all run on the event loop.
    """

    started_at: datetime
    session_id: str = field(default_factory=lambda: uuid4().hex)
    member_id: str | None = None
    off_reason: str | None = None
    directory: str | None = None
    subscribed: bool = False
    #: When the last channel event still waiting for an answer was attempted.
    attempt_at: datetime | None = None
    #: When an ``inbox`` call first followed an attempted event; sticky.
    push_confirmed_at: datetime | None = None
    resolved: anyio.Event = field(default_factory=anyio.Event)


class BusyWarning:
    """A ``StoreBusyError`` is logged once per run of failures, not once per tick."""

    def __init__(self, what: str) -> None:
        self._what = what
        self._warned = False

    def failed(self, error: StoreBusyError) -> None:
        if not self._warned:
            logger.warning("%s: store busy, retrying: %s", self._what, error)
            self._warned = True

    def cleared(self) -> None:
        self._warned = False


async def resolve_presence(state: PresenceState, deps: PresenceDeps) -> None:
    """Resolve the member once (D3); ``state.resolved`` is set in every outcome.

    Raises:
        ContextForgeError: ``cf`` failed or timed out.
        StoreError: The member lookup failed.
    """
    try:
        try:
            found = await anyio.to_thread.run_sync(
                lookup_member, deps.open_store, deps.cf_run
            )
        except Exception:
            state.off_reason = "the member lookup failed"
            logger.exception("no presence: %s", state.off_reason)
            raise
        state.directory = str(found.directory)
        if found.member_id is not None:
            state.member_id = found.member_id
        else:
            state.off_reason = f"{found.directory} is not a member"
            logger.info("no presence: %s (%s)", state.off_reason, found.detail)
    finally:
        state.resolved.set()


def client_name(name: str | None) -> str:
    """``name`` when ``list`` may show it, else the placeholder with one WARNING."""
    if name is not None and CLIENT_NAME_PATTERN.fullmatch(name):
        return name
    logger.warning(
        "client name %r is not displayable; stored as %s", name, UNRECOGNIZED_CLIENT
    )
    return UNRECOGNIZED_CLIENT


def _session(state: PresenceState, client: str, now: datetime) -> Session:
    if state.member_id is None or state.directory is None:
        raise ValueError("a session row needs a resolved member and directory")
    return Session(
        session_id=state.session_id,
        member_id=state.member_id,
        client=client,
        directory=state.directory,
        started_at=state.started_at,
        heartbeat_at=now,
        push_confirmed_at=state.push_confirmed_at,
    )


async def heartbeat_loop(state: PresenceState, deps: PresenceDeps, client: str) -> None:
    """Beat now, then every ``session_heartbeat_seconds``, until cancelled.

    Raises:
        StoreError: Any store failure but a busy store.
    """
    busy = BusyWarning("session heartbeat")
    while True:
        session = _session(state, client, deps.clock())
        try:
            await anyio.to_thread.run_sync(
                beat_session,
                deps.open_store,
                session,
                deps.timing.session_stale_seconds,
            )
            busy.cleared()
        except StoreBusyError as error:
            # Push is a hint and polling is the floor: a missed beat is retried at
            # the next one, and the first that succeeds re-creates a pruned row.
            busy.failed(error)
        await anyio.sleep(deps.timing.session_heartbeat_seconds)


def _answer_limit() -> timedelta:
    return timedelta(seconds=PUSH_ANSWER_SECONDS)


def note_event_attempted(state: PresenceState, now: datetime) -> None:
    """Record an attempted channel event, unless one is still waiting for an answer.

    An unanswered attempt older than ``PUSH_ANSWER_SECONDS`` is replaced.
    """
    waiting = state.attempt_at
    if waiting is None or now - waiting > _answer_limit():
        state.attempt_at = now


def note_inbox_called(state: PresenceState, now: datetime) -> None:
    """An ``inbox`` call completed: it confirms push if it follows a recent attempt.

    Confirmation means "an ``inbox`` call followed an attempted event", not proof
    the event reached the agent: the client gives no delivery signal, so an agent
    calling ``inbox`` for its own reasons inside the window also confirms (D6
    accepts that misread). Confirmation is sticky; the attempt is cleared either way.
    """
    waiting = state.attempt_at
    answered = waiting is not None and now - waiting <= _answer_limit()
    if answered and state.push_confirmed_at is None:
        state.push_confirmed_at = now
    state.attempt_at = None


@dataclass(frozen=True)
class ToolPresence:
    """What ``call_tool`` needs of presence: the state and the clock (D6)."""

    state: PresenceState
    clock: Callable[[], datetime]

    def inbox_called(self) -> None:
        note_inbox_called(self.state, self.clock())
