"""A rig for the presence tests (slice 241): a fake clock, a throwaway store with one
member, an opener that can be made to fail or block, and short intervals."""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

import anyio
import mcp_types as types
from cf_fixtures import DEFAULT_WORKTREE, fake_cf_run, fixture_document
from mcp.server.connection import Connection
from mcp.shared.dispatcher import CallOptions
from mcp_types.version import LATEST_HANDSHAKE_VERSION
from store.message_support import send_request

from amoeba.mcp.presence import (
    PresenceDeps,
    PresenceState,
    SessionTiming,
    ToolPresence,
)
from amoeba.store.deliveries import write_delivery
from amoeba.store.models import MemberSettings, Session
from amoeba.store.programs import upsert_member, upsert_program
from amoeba.store.sessions import live_sessions
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, RulesFrom
from amoeba.upstream.context_forge.cli_call import CfRun

START: Final = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
#: The member the recorded ``cf get`` output resolves to.
MEMBER_ID: Final[str] = fixture_document(DEFAULT_WORKTREE)["id"]
PROGRAM_ID: Final = "demo"
#: The second member, who sends the mail a test delivers.
PEER: Final = "peer-member"
#: Short real intervals, so a loop turns many times in a test.
FAST: Final = SessionTiming(
    notify_poll_seconds=0.01,
    session_heartbeat_seconds=0.02,
    session_stale_seconds=90,
)
#: How long a test waits for a loop to reach a state before failing.
WAIT_SECONDS: Final = 5.0


@dataclass
class FakeClock:
    now: datetime = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@dataclass
class Opener:
    """Opens the throwaway store. Each queued entry answers one open: an error is
    raised instead, ``None`` opens normally. While ``block`` is set an open waits on
    it (a store held elsewhere). ``on_open`` runs first with the open's number, so a
    test can write between two reads."""

    path: Path
    errors: list[Exception | None] = field(default_factory=lambda: [])
    block: threading.Event | None = None
    on_open: Callable[[int], None] | None = None
    opens: int = 0

    def __call__(self) -> Store:
        self.opens += 1
        if self.on_open is not None:
            self.on_open(self.opens)
        if self.block is not None:
            self.block.wait()
        queued = self.errors.pop(0) if self.errors else None
        if queued is not None:
            raise queued
        return Store.open(self.path)


def seed_member(path: Path, member_id: str = MEMBER_ID) -> None:
    with Store.open(path) as store, store.write() as transaction:
        upsert_program(
            transaction,
            program_id=PROGRAM_ID,
            concept_member=None,
            concept_path=None,
            now=START,
        )
        upsert_member(
            transaction,
            program_id=PROGRAM_ID,
            settings=MemberSettings(
                project_id=member_id,
                rules_paths=("CLAUDE.md",),
                authorize_allow=(),
                authorize_deny=(),
                rules_from=RulesFrom.NAMED,
                wake_command=None,
            ),
            now=START,
        )


def deliver(path: Path, *events: DeliveryEvent, message: str = "req") -> None:
    """Deliver ``events`` (one ``SENT`` by default) of a request from ``PEER``,
    sending the request first if ``message`` is new."""
    with Store.open(path) as store, store.write() as transaction:
        if (
            transaction.execute(
                "SELECT 1 FROM messages WHERE message_id = ?", (message,)
            ).fetchone()
            is None
        ):
            send_request(transaction, message, from_member=PEER, to_member=MEMBER_ID)
        for event in events or (DeliveryEvent.SENT,):
            write_delivery(transaction, MEMBER_ID, message, event, START)


def timed_out_cf(
    argv: Sequence[str], **_kwargs: object
) -> subprocess.CompletedProcess[str]:
    """A ``cf`` run that times out."""
    raise subprocess.TimeoutExpired(list(argv), 30)


def make_deps(
    opener: Opener,
    clock: FakeClock,
    *,
    cf_run: CfRun | None = None,
    timing: SessionTiming = FAST,
) -> PresenceDeps:
    return PresenceDeps(
        open_store=opener,
        cf_run=cf_run if cf_run is not None else fake_cf_run(DEFAULT_WORKTREE),
        clock=clock,
        timing=timing,
    )


def member_state(clock: FakeClock, directory: Path) -> PresenceState:
    """A state already resolved to the member, as the heartbeat finds it."""
    state = PresenceState(started_at=clock())
    state.member_id = MEMBER_ID
    state.directory = str(directory)
    state.resolved.set()
    return state


def sessions_in(path: Path, now: datetime, stale_seconds: float) -> tuple[Session, ...]:
    with Store.open(path) as store, store.read() as transaction:
        return live_sessions(transaction, now, stale_seconds)


def all_session_rows(path: Path) -> list[tuple[object, ...]]:
    with Store.open(path) as store, store.read() as transaction:
        return transaction.execute(
            "SELECT session_id, client, started_at, heartbeat_at, push_confirmed_at "
            "FROM sessions"
        ).fetchall()


async def eventually(condition: Callable[[], bool], what: str) -> None:
    """Wait, in real time, until ``condition`` holds.

    A poll, not an event: the state watched (store rows, log records) is written by
    worker threads and the code under test, which signal nothing.
    """
    with anyio.fail_after(WAIT_SECONDS):
        while not condition():  # noqa: ASYNC110 - see the docstring
            await anyio.sleep(0.005)
    assert condition(), what


@dataclass
class RecordingOutbound:
    """The connection's channel to the client: records each notification sent, or
    raises ``error`` from ``notify``."""

    sent: list[tuple[str, dict[str, Any]]] = field(default_factory=lambda: [])
    error: BaseException | None = None

    async def send_raw_request(
        self,
        method: str,
        params: Mapping[str, Any] | None,
        opts: CallOptions | None = None,
    ) -> dict[str, Any]:
        raise AssertionError(f"presence sends no requests, got {method}")

    async def notify(
        self,
        method: str,
        params: Mapping[str, Any] | None,
        opts: CallOptions | None = None,
    ) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append((method, dict(params or {})))

    def methods(self) -> list[str]:
        return [method for method, _ in self.sent]


def make_connection(
    outbound: RecordingOutbound, client: str = "claude-code"
) -> Connection:
    """A handshake-era connection whose client sent ``client`` as its name; call it
    inside the event loop (it makes an ``anyio.Event``)."""
    return Connection(
        outbound,
        protocol_version=LATEST_HANDSHAKE_VERSION,
        client_params=types.InitializeRequestParams(
            protocol_version=LATEST_HANDSHAKE_VERSION,
            capabilities=types.ClientCapabilities(),
            client_info=types.Implementation(name=client, version="0"),
        ),
    )


def idle_presence() -> ToolPresence:
    """Presence for a tool test that is not about it; call inside the event loop."""
    return ToolPresence(PresenceState(started_at=START), FakeClock())
