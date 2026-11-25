"""A rig for the presence tests (slice 241): a fake clock, a throwaway store with one
member, an opener that can be made to fail or block, and short intervals."""

from __future__ import annotations

import inspect
import subprocess
import tempfile
import threading
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
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
from operations.status_support import status_deps
from store.message_support import send_request
from store.seed import insert_checkout
from store_open import open_local_store
from user_configs import user_config

from amoeba.config.user_config import UserConfig
from amoeba.mcp.presence import PresenceDeps, PresenceState, ToolPresence
from amoeba.operations.deps import Deps
from amoeba.operations.steps.dispatch import StepEdges
from amoeba.operations.store_steps import LocalSteps, Steps
from amoeba.store.deliveries import write_delivery
from amoeba.store.models import MemberSettings, Session
from amoeba.store.programs import upsert_member, upsert_program
from amoeba.store.sessions import live_sessions
from amoeba.store.vocabulary import DeliveryEvent, RulesFrom
from amoeba.upstream.context_forge.cli_call import CfRun
from amoeba.wiring_presence import LastReply, SessionIdentity

START: Final = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
#: The member the recorded ``cf get`` output resolves to.
MEMBER_ID: Final[str] = fixture_document(DEFAULT_WORKTREE)["id"]
PROGRAM_ID: Final = "demo"
#: The second member, who sends the mail a test delivers.
PEER: Final = "peer-member"
#: The config the local steps read: short real intervals, so a loop turns many times
#: in a test.
FAST: Final[UserConfig] = user_config().model_copy(
    update={
        "notify_poll_seconds": 0.01,
        "session_heartbeat_seconds": 0.02,
        "session_stale_seconds": 90,
    }
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
    """Opens the steps one worker thread uses, on a throwaway store: each call opens
    its own store and ``LocalSteps`` and closes both when the thread is done, as
    ``wiring.session_step_source`` does. Each queued entry answers one open: an error
    is raised instead, ``None`` opens normally. While ``block`` is set an open waits on
    it (a store held elsewhere). ``on_open`` runs first with the open's number, so a
    test can write between two ticks. ``make_deps`` binds the clock and the config.
    """

    path: Path
    errors: list[Exception | None] = field(default_factory=lambda: [])
    block: threading.Event | None = None
    on_open: Callable[[int], None] | None = None
    opens: int = 0
    #: The identity each open was given, in order.
    identities: list[SessionIdentity | None] = field(default_factory=lambda: [])
    clock: Callable[[], datetime] | None = None
    config: UserConfig = FAST

    @contextmanager
    def __call__(
        self, last: LastReply, identity: SessionIdentity | None
    ) -> Generator[Steps]:
        self.opens += 1
        self.identities.append(identity)
        if self.on_open is not None:
            self.on_open(self.opens)
        if self.block is not None:
            self.block.wait()
        queued = self.errors.pop(0) if self.errors else None
        if queued is not None:
            raise queued
        if self.clock is None:
            raise AssertionError("bind the opener's clock with make_deps")
        with open_local_store(self.path) as store:
            yield LocalSteps(store, StepEdges(self.clock, lambda: self.config))


def raise_when_called_from(
    function: str, errors: list[Exception]
) -> Callable[[int], None]:
    """An ``Opener.on_open`` that raises the queued ``errors`` one at a time, but only
    for an open made under the worker function ``function`` (the tick's ``work``, the
    exit's ``_end_in_thread``, the runner's ``_body``): the three open steps at once,
    so a queue shared by number would hand an error to whichever thread asks first."""

    def hook(_number: int) -> None:
        if errors and any(frame.function == function for frame in inspect.stack()):
            raise errors.pop(0)

    return hook


def seed_member(path: Path, member_id: str = MEMBER_ID) -> None:
    with open_local_store(path) as store, store.write() as transaction:
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
            ),
            name=member_id,
            now=START,
        )
        # The stub ``cf`` answers a directory with the member's own id.
        insert_checkout(
            transaction,
            member_id=member_id,
            cf_project_id=member_id,
            path=f"/work/{member_id}",
            now=START,
        )


def deliver(path: Path, *events: DeliveryEvent, message: str = "req") -> None:
    """Deliver ``events`` (one ``SENT`` by default) of a request from ``PEER``,
    sending the request first if ``message`` is new."""
    with open_local_store(path) as store, store.write() as transaction:
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


_AFTER_DIRECTORY: Final = tempfile.TemporaryDirectory()


def _after_deps() -> Deps:
    """The after-step's edges: fakes, with nothing running and nothing to prune."""
    return status_deps(
        Path(_AFTER_DIRECTORY.name), cf=fake_cf_run(DEFAULT_WORKTREE), runs=[]
    )


def make_deps(
    opener: Opener,
    clock: Callable[[], datetime],
    *,
    cf_run: CfRun | None = None,
    config: UserConfig = FAST,
    after_deps: Callable[[], Deps] = _after_deps,
) -> PresenceDeps:
    opener.clock, opener.config = clock, config
    return PresenceDeps(
        open_steps=opener,
        cf_run=cf_run if cf_run is not None else fake_cf_run(DEFAULT_WORKTREE),
        clock=clock,
        after_deps=after_deps,
    )


def member_state(clock: FakeClock, directory: Path) -> PresenceState:
    """A state in ``directory``, as the presence task leaves it before the first
    tick: nothing known yet (the member comes from the tick's reply)."""
    state = PresenceState(started_at=clock())
    state.directory = str(directory)
    return state


def sessions_in(path: Path, now: datetime, stale_seconds: float) -> tuple[Session, ...]:
    with open_local_store(path) as store, store.read() as transaction:
        return live_sessions(transaction, now, stale_seconds)


def all_session_rows(path: Path) -> list[tuple[object, ...]]:
    with open_local_store(path) as store, store.read() as transaction:
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
