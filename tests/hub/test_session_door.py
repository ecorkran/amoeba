"""A session's tick through ``DoorSteps`` against an in-process hub (slice 263, D1, D5,
D6): the hub's clock is the only one that stamps a session, a baseline is kept per way,
and a hub that is down is only a skipped tick."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import anyio
import pytest
from mcp_server.presence_rig import (
    FAST,
    MEMBER_ID,
    START,
    FakeClock,
    RecordingOutbound,
    eventually,
    member_state,
    seed_member,
)

from amoeba.config.home import state_layout
from amoeba.store.vocabulary import DeliveryEvent
from hub.call_support import NOW
from hub.in_process_hub import InProcessHub
from hub.session_door_support import (
    CLIENT,
    QUIET_SECONDS,
    deliver,
    deps,
    events,
    hub_sessions,
    join,
    serving_hub,
    ticking,
)


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[InProcessHub]:
    with serving_hub(tmp_path) as serving:
        yield serving


def test_a_tick_through_the_door_writes_the_row_with_the_hubs_time(
    hub: InProcessHub, tmp_path: Path
) -> None:
    join(hub)
    clock = FakeClock()
    state = member_state(clock, tmp_path)

    async def scenario() -> None:
        await eventually(lambda: state.as_of_seq is not None, "a reply")
        assert state.way == "door"
        assert state.member_id == MEMBER_ID

    anyio.run(ticking, deps(clock), state, RecordingOutbound(), scenario)

    assert hub_sessions(hub) == [(MEMBER_ID, NOW, CLIENT)]
    assert clock() == START != NOW


def test_a_client_file_appearing_between_two_ticks_is_a_new_baseline_with_no_event(
    hub: InProcessHub, tmp_path: Path
) -> None:
    layout = state_layout()
    seed_member(layout.store_path)
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    outbound = RecordingOutbound()
    deliver(hub, "waiting-on-the-hub")

    async def scenario() -> None:
        await eventually(lambda: state.way == "local", "a tick on the local store")
        join(hub)
        await eventually(lambda: state.way == "door", "a tick on the door")
        await anyio.sleep(QUIET_SECONDS)
        assert events(outbound) == []
        assert state.last_seen == 1
        deliver(hub, "after-the-baseline", DeliveryEvent.SENT)
        await eventually(lambda: bool(events(outbound)), "an event after it")

    anyio.run(ticking, deps(clock), state, outbound, scenario)

    assert len(events(outbound)) == 1


def test_a_hub_that_is_down_skips_ticks_and_the_first_after_returns_all_above_last_seen(
    hub: InProcessHub, tmp_path: Path
) -> None:
    join(hub)
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: state.as_of_seq is not None, "the baseline")
        baseline = state.last_seen
        hub.stop()
        await eventually(lambda: state.last_error is not None, "a skipped tick")
        assert state.last_seen == baseline
        deliver(hub, "first-while-down", DeliveryEvent.SENT)
        deliver(hub, "second-while-down", DeliveryEvent.SENT)
        await anyio.sleep(QUIET_SECONDS)
        assert events(outbound) == []
        hub.start()
        await eventually(lambda: bool(events(outbound)), "an event once it is back")

    anyio.run(ticking, deps(clock), state, outbound, scenario)

    (event,) = events(outbound)
    assert event["meta"]["count"] == "2"
    assert state.last_error is None


def test_a_client_clock_an_hour_ahead_is_listed_on_the_hubs_times_and_goes_stale(
    hub: InProcessHub, tmp_path: Path
) -> None:
    join(hub)
    clock = FakeClock(now=NOW + timedelta(hours=1))
    state = member_state(clock, tmp_path)

    async def scenario() -> None:
        await eventually(lambda: state.as_of_seq is not None, "a reply")

    anyio.run(ticking, deps(clock), state, RecordingOutbound(), scenario)

    assert hub_sessions(hub) == [(MEMBER_ID, NOW, CLIENT)]
    assert hub_sessions(hub, FAST.session_stale_seconds - 1) != []
    assert hub_sessions(hub, FAST.session_stale_seconds + 1) == []
