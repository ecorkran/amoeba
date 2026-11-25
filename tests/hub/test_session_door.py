"""A session's tick through ``DoorSteps`` against an in-process hub (slice 263, D1, D5,
D6): the hub's clock is the only one that stamps a session, a baseline is kept per way,
and a hub that is down is only a skipped tick."""

from __future__ import annotations

import shutil
from collections.abc import Awaitable, Callable, Iterator
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Any

import anyio
import pytest
from cf_fixtures import DEFAULT_WORKTREE, fake_cf_run
from mcp_server.presence_rig import (
    FAST,
    MEMBER_ID,
    START,
    FakeClock,
    RecordingOutbound,
    eventually,
    make_connection,
    member_state,
    seed_member,
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


def _no_spawn(work: Callable[[], Awaitable[None]]) -> None:
    """An after-step is not what these tests are about."""


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[InProcessHub]:
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


def _join(hub: InProcessHub) -> None:
    """The client files `amoeba join` writes, with the local store left in place."""
    layout = state_layout()
    shutil.copyfile(hub.cert_path, layout.pinned_cert)
    write_client_file(
        layout.client_file,
        ClientFile(address=hub.address, machine="alpha", token=ALPHA_TOKEN),
    )


def _deliver(hub: InProcessHub, message: str, *events: DeliveryEvent) -> None:
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


def _deps(clock: FakeClock) -> PresenceDeps:
    layout = state_layout()
    return PresenceDeps(
        open_steps=lambda last, identity: steps_for(
            layout, last, lambda: FAST, TICK_TIMES, identity
        ),
        cf_run=fake_cf_run(DEFAULT_WORKTREE),
        clock=clock,
        after_deps=partial(wiring.default_deps, layout),
    )


async def _ticking(
    deps: PresenceDeps,
    state: PresenceState,
    outbound: RecordingOutbound,
    scenario: Callable[[], Awaitable[None]],
) -> None:
    connection = make_connection(outbound)
    runner = AfterRunner(deps, _no_spawn)
    async with anyio.create_task_group() as group:
        group.start_soon(run_ticks, connection, state, deps, CLIENT, runner)
        await scenario()
        group.cancel_scope.cancel()


def _events(outbound: RecordingOutbound) -> list[dict[str, Any]]:
    return [params for method, params in outbound.sent if method == CHANNEL_METHOD]


def _hub_sessions(hub: InProcessHub, now_offset: float = 0) -> list[tuple[Any, ...]]:
    """The live rows at the hub's clock, plus ``now_offset`` seconds."""
    at = hub.rig.clock() + timedelta(seconds=now_offset)
    with hub.rig.open_store() as store, store.read() as transaction:
        return [
            (row.member_id, row.heartbeat_at, row.client)
            for row in live_sessions(transaction, at, FAST.session_stale_seconds)
        ]


def test_a_tick_through_the_door_writes_the_row_with_the_hubs_time(
    hub: InProcessHub, tmp_path: Path
) -> None:
    _join(hub)
    clock = FakeClock()
    state = member_state(clock, tmp_path)

    async def scenario() -> None:
        await eventually(lambda: state.as_of_seq is not None, "a reply")
        assert state.way == "door"
        assert state.member_id == MEMBER_ID

    anyio.run(_ticking, _deps(clock), state, RecordingOutbound(), scenario)

    assert _hub_sessions(hub) == [(MEMBER_ID, NOW, CLIENT)]
    assert clock() == START != NOW


def test_a_client_file_appearing_between_two_ticks_is_a_new_baseline_with_no_event(
    hub: InProcessHub, tmp_path: Path
) -> None:
    layout = state_layout()
    seed_member(layout.store_path)
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    outbound = RecordingOutbound()
    _deliver(hub, "waiting-on-the-hub")

    async def scenario() -> None:
        await eventually(lambda: state.way == "local", "a tick on the local store")
        _join(hub)
        await eventually(lambda: state.way == "door", "a tick on the door")
        await anyio.sleep(QUIET_SECONDS)
        assert _events(outbound) == []
        assert state.last_seen == 1
        _deliver(hub, "after-the-baseline", DeliveryEvent.SENT)
        await eventually(lambda: bool(_events(outbound)), "an event after it")

    anyio.run(_ticking, _deps(clock), state, outbound, scenario)

    assert len(_events(outbound)) == 1


def test_a_hub_that_is_down_skips_ticks_and_the_first_after_returns_all_above_last_seen(
    hub: InProcessHub, tmp_path: Path
) -> None:
    _join(hub)
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: state.as_of_seq is not None, "the baseline")
        baseline = state.last_seen
        hub.stop()
        await eventually(lambda: state.last_error is not None, "a skipped tick")
        assert state.last_seen == baseline
        _deliver(hub, "first-while-down", DeliveryEvent.SENT)
        _deliver(hub, "second-while-down", DeliveryEvent.SENT)
        await anyio.sleep(QUIET_SECONDS)
        assert _events(outbound) == []
        hub.start()
        await eventually(lambda: bool(_events(outbound)), "an event once it is back")

    anyio.run(_ticking, _deps(clock), state, outbound, scenario)

    (event,) = _events(outbound)
    assert event["meta"]["count"] == "2"
    assert state.last_error is None


def test_a_client_clock_an_hour_ahead_is_listed_on_the_hubs_times_and_goes_stale(
    hub: InProcessHub, tmp_path: Path
) -> None:
    _join(hub)
    clock = FakeClock(now=NOW + timedelta(hours=1))
    state = member_state(clock, tmp_path)

    async def scenario() -> None:
        await eventually(lambda: state.as_of_seq is not None, "a reply")

    anyio.run(_ticking, _deps(clock), state, RecordingOutbound(), scenario)

    assert _hub_sessions(hub) == [(MEMBER_ID, NOW, CLIENT)]
    assert _hub_sessions(hub, FAST.session_stale_seconds - 1) != []
    assert _hub_sessions(hub, FAST.session_stale_seconds + 1) == []
