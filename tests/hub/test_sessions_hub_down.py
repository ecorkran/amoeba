"""A session while the hub is down, on an in-process hub the test stops and starts
(slice 263, 8.3, D4, D5): the ticks are bounded, mail written just before the stop is
pushed by the first tick after, and a stale row is listed again from the next tick."""

from __future__ import annotations

import threading
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

import anyio
import pytest
from mcp_server.presence_rig import (
    FAST,
    MEMBER_ID,
    FakeClock,
    RecordingOutbound,
    eventually,
    member_state,
)

from amoeba.mcp.presence import PresenceDeps
from amoeba.operations.store_steps import Steps
from amoeba.store.vocabulary import DeliveryEvent
from amoeba.wiring_presence import LastReply, SessionIdentity
from hub.in_process_hub import InProcessHub
from hub.session_door_support import (
    deliver,
    deps,
    events,
    hub_sessions,
    join,
    serving_hub,
    ticking,
)

POLL = 0.2
HUB_CONFIG = FAST.model_copy(
    update={
        "notify_poll_seconds": POLL,
        "session_heartbeat_seconds": 0.4,
        "session_stale_seconds": 90,
    }
)
DOWN_SECONDS = 3.0


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[InProcessHub]:
    with serving_hub(tmp_path) as serving:
        serving.rig.config = lambda: HUB_CONFIG
        yield serving


@dataclass
class Calls:
    """How many tick calls were opened, and how many were open at once."""

    opened: int = 0
    open_now: int = 0
    peak: int = 0
    lock: threading.Lock = threading.Lock()  # noqa: RUF009


def _counted(base: PresenceDeps, calls: Calls) -> PresenceDeps:
    inner = base.open_steps

    @contextmanager
    def counting(last: LastReply, identity: SessionIdentity | None) -> Generator[Steps]:
        with calls.lock:
            calls.opened += 1
            calls.open_now += 1
            calls.peak = max(calls.peak, calls.open_now)
        try:
            with inner(last, identity) as steps:
                yield steps
        finally:
            with calls.lock:
                calls.open_now -= 1

    return replace(base, open_steps=counting)


def test_a_stopped_hub_has_at_most_one_tick_in_flight_and_bounded_attempts(
    hub: InProcessHub, tmp_path: Path
) -> None:
    join(hub)
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    calls = Calls()
    counted: list[int] = []

    async def scenario() -> None:
        await eventually(lambda: state.as_of_seq is not None, "the baseline")
        hub.stop()
        before = calls.opened
        await anyio.sleep(DOWN_SECONDS)
        counted.append(calls.opened - before)
        assert state.last_error is not None
        hub.start()
        await eventually(lambda: state.last_error is None, "a tick once it is back")

    anyio.run(
        ticking, _counted(deps(clock), calls), state, RecordingOutbound(), scenario
    )

    assert calls.peak == 1
    assert counted[0] <= DOWN_SECONDS / POLL + 1


def test_mail_written_just_before_the_stop_is_pushed_by_the_first_tick_after(
    hub: InProcessHub, tmp_path: Path
) -> None:
    join(hub)
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    outbound = RecordingOutbound()

    async def first_pass() -> None:
        await eventually(lambda: state.as_of_seq is not None, "the baseline")

    anyio.run(ticking, deps(clock), state, outbound, first_pass)
    deliver(hub, "just-before", DeliveryEvent.SENT)
    hub.stop()
    hub.start()

    async def second_pass() -> None:
        await eventually(lambda: bool(events(outbound)), "the event after the restart")

    anyio.run(ticking, deps(clock), state, outbound, second_pass)

    (event,) = events(outbound)
    assert event["meta"]["count"] == "1"


def test_a_row_stale_while_the_hub_was_down_is_listed_again_from_the_next_tick(
    hub: InProcessHub, tmp_path: Path
) -> None:
    join(hub)
    clock = FakeClock()
    state = member_state(clock, tmp_path)

    async def pass_until_a_reply() -> None:
        await eventually(lambda: state.as_of_seq is not None, "a reply")

    anyio.run(ticking, deps(clock), state, RecordingOutbound(), pass_until_a_reply)
    assert [row[0] for row in hub_sessions(hub)] == [MEMBER_ID]

    hub.stop()
    hub.rig.advance(seconds=HUB_CONFIG.session_stale_seconds + 1)
    hub.start()

    assert hub_sessions(hub) == []

    async def pass_until_listed() -> None:
        await eventually(lambda: bool(hub_sessions(hub)), "the row listed again")

    anyio.run(ticking, deps(clock), state, RecordingOutbound(), pass_until_listed)
    assert [row[0] for row in hub_sessions(hub)] == [MEMBER_ID]
