"""The in-process hub and the ticking helpers the session door tests share
(slice 263, D1, D5, D6)."""

from __future__ import annotations

import shutil
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Any

import anyio
from cf_fixtures import DEFAULT_WORKTREE, fake_cf_run
from mcp_server.presence_rig import (
    FAST,
    MEMBER_ID,
    FakeClock,
    RecordingOutbound,
    make_connection,
)
from store.decision_support import CORE, TRADING
from store.message_support import send_request
from store.seed import insert_checkout, insert_member

from amoeba import wiring
from amoeba.client.client_file import ClientFile, write_client_file
from amoeba.config.home import state_layout
from amoeba.mcp.after_runner import AfterRunner
from amoeba.mcp.channel_event import CHANNEL_METHOD
from amoeba.mcp.presence import PresenceDeps, PresenceState
from amoeba.mcp.tick import run_ticks
from amoeba.store.deliveries import write_delivery
from amoeba.store.sessions import live_sessions
from amoeba.store.vocabulary import DeliveryEvent
from amoeba.wire.times import TICK_TIMES
from amoeba.wiring_steps import steps_for
from hub.call_support import ALPHA_TOKEN, NOW
from hub.in_process_hub import InProcessHub

CLIENT = "claude-code"
QUIET_SECONDS = 0.15


def no_spawn(work: Callable[[], Awaitable[None]]) -> None:
    """An after-step is not what these tests are about."""


@contextmanager
def serving_hub(tmp_path: Path) -> Generator[InProcessHub]:
    """A serving hub whose member is the one the stub ``cf`` names, ticking fast. The
    machine is not joined: a test joins it when it wants the door."""
    with InProcessHub(tmp_path / "hub") as serving:
        serving.rig.config = lambda: FAST
        with serving.rig.open_store() as store:
            alpha = serving.rig.machine(ALPHA_TOKEN)
            assert alpha is not None
            store.act_as(alpha)
            with store.write() as transaction:
                insert_member(
                    transaction,
                    project_id=MEMBER_ID,
                    program_id=TRADING,
                    rules_paths=(),
                    authorize_allow=(),
                    authorize_deny=(),
                    registered_at=NOW,
                    updated_at=NOW,
                    name="the-member",
                )
                insert_checkout(
                    transaction,
                    member_id=MEMBER_ID,
                    cf_project_id=MEMBER_ID,
                    path="/work/the-member",
                    now=NOW,
                )
        yield serving


def join(hub: InProcessHub) -> None:
    """The client files `amoeba join` writes, with the local store left in place."""
    layout = state_layout()
    shutil.copyfile(hub.cert_path, layout.pinned_cert)
    write_client_file(
        layout.client_file,
        ClientFile(address=hub.address, machine="alpha", token=ALPHA_TOKEN),
    )


def deliver(hub: InProcessHub, message: str, *events: DeliveryEvent) -> None:
    """Deliveries for the member on the hub, written as the hub's machine."""
    with hub.rig.open_store() as store:
        alpha = hub.rig.machine(ALPHA_TOKEN)
        assert alpha is not None
        store.act_as(alpha)
        with store.write() as transaction:
            send_request(
                transaction, message, from_member=CORE, to_member=MEMBER_ID, now=NOW
            )
            for event in events or (DeliveryEvent.SENT,):
                write_delivery(transaction, MEMBER_ID, message, event, NOW)


def deps(clock: FakeClock) -> PresenceDeps:
    layout = state_layout()
    return PresenceDeps(
        open_steps=lambda last, identity: steps_for(
            layout, last, lambda: FAST, TICK_TIMES, identity
        ),
        cf_run=fake_cf_run(DEFAULT_WORKTREE),
        clock=clock,
        after_deps=partial(wiring.default_deps, layout),
    )


async def ticking(
    deps: PresenceDeps,
    state: PresenceState,
    outbound: RecordingOutbound,
    scenario: Callable[[], Awaitable[None]],
) -> None:
    connection = make_connection(outbound)
    runner = AfterRunner(deps, no_spawn)
    async with anyio.create_task_group() as group:
        group.start_soon(run_ticks, connection, state, deps, CLIENT, runner)
        await scenario()
        group.cancel_scope.cancel()


def events(outbound: RecordingOutbound) -> list[dict[str, Any]]:
    return [params for method, params in outbound.sent if method == CHANNEL_METHOD]


def hub_sessions(hub: InProcessHub, now_offset: float = 0) -> list[tuple[Any, ...]]:
    """The live rows at the hub's clock, plus ``now_offset`` seconds."""
    at = hub.rig.clock() + timedelta(seconds=now_offset)
    with hub.rig.open_store() as store, store.read() as transaction:
        return [
            (row.member_id, row.heartbeat_at, row.client)
            for row in live_sessions(transaction, at, FAST.session_stale_seconds)
        ]
