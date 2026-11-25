"""Presence: what a serving session knows of its member and its push (slice 241, D2,
D6; slice 263, D1, D3, D4).

Only event-loop tasks touch ``PresenceState``. The tick (``mcp.tick``) updates it from
each reply, the resource handlers and the tools read it, and every step and ``cf`` call
runs in a worker thread that opens its own steps, so the loop only sleeps, sends and
keeps books.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Final
from uuid import uuid4

import anyio

from amoeba.wire.protocol import CLIENT_NAME_PATTERN
from amoeba.wiring_presence import CfRun, Deps, StepSource

logger = logging.getLogger(__name__)

#: How long after an attempted channel event an ``inbox`` call still answers it: a
#: queued event waits for the agent's current turn to end (D6).
PUSH_ANSWER_SECONDS: Final = 300
#: A ``clientInfo.name`` not matching ``CLIENT_NAME_PATTERN`` is stored as this.
UNRECOGNIZED_CLIENT: Final = "unrecognized"


@dataclass(frozen=True)
class PresenceDeps:
    """What presence needs from outside; a test substitutes each."""

    #: The steps one worker thread uses, opened and closed in that thread.
    open_steps: StepSource
    cf_run: CfRun
    clock: Callable[[], datetime]
    #: The operation deps the after-step is given (``wiring.default_deps``).
    after_deps: Callable[[], Deps]


@dataclass
class PresenceState:
    """The server's presence: what the newest tick reply said.

    ``resolved`` is set once the first tick ends, however it ends, so a handler
    waiting on it always stops waiting. Read by the resource handlers, written by the
    tick and ``call_tool``; all run on the event loop.
    """

    started_at: datetime
    session_id: str = field(default_factory=lambda: uuid4().hex)
    #: The newest reply's member and its name; ``None`` with no member or no reply.
    member_id: str | None = None
    member_name: str | None = None
    #: Why the newest reply had no member.
    off_reason: str | None = None
    directory: str | None = None
    subscribed: bool = False
    #: The newest reply's ``as_of_seq``; ``None`` until a tick has had a reply.
    as_of_seq: int | None = None
    #: The newest tick's failure, as ``<ErrorName>: <text>``; cleared by a reply.
    last_error: str | None = None
    #: Whether a reply ever named a member: the session then ends its row at exit.
    told_member: bool = False
    #: The poll interval the newest reply gave; ``None`` before the first reply.
    poll_seconds: float | None = None
    #: The way (door or local), the member and the highest delivery number the last
    #: reply left this session at: the baseline the next request builds on.
    way: str | None = None
    baseline_member: str | None = None
    last_seen: int | None = None
    #: When the last channel event still waiting for an answer was attempted.
    attempt_at: datetime | None = None
    #: When an ``inbox`` call first followed an attempted event; sticky.
    push_confirmed_at: datetime | None = None
    resolved: anyio.Event = field(default_factory=anyio.Event)


class FailureLog:
    """One WARNING when a run of failures starts or its error type changes, one INFO
    when the next attempt succeeds (263 D4): a refused call repeated every poll
    interval is one line, not one per tick."""

    def __init__(self, what: str) -> None:
        self._what = what
        self._failing: str | None = None

    def failed(self, error: Exception) -> None:
        kind = type(error).__name__
        if kind != self._failing:
            logger.warning("%s failed: %s: %s", self._what, kind, error)
        self._failing = kind

    def recovered(self) -> None:
        if self._failing is not None:
            logger.info("%s recovered", self._what)
        self._failing = None


def client_name(name: str | None) -> str:
    """``name`` when ``list`` may show it, else the placeholder with one WARNING."""
    if name is not None and CLIENT_NAME_PATTERN.fullmatch(name):
        return name
    logger.warning(
        "client name %r is not displayable; stored as %s", name, UNRECOGNIZED_CLIENT
    )
    return UNRECOGNIZED_CLIENT


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
    The window is the client's own measure: only whether it was met (``push_confirmed``)
    crosses the door.
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
