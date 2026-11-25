"""Push and presence across two machines, on real processes (slice 263, 8.2): a real
hub, real ``amoeba-mcp`` servers over stdio, and the real CLI on each machine."""

from __future__ import annotations

import os
import signal
import time
from collections.abc import Iterator
from pathlib import Path

import anyio
import pytest
from hub_fixture import FIRST, SECOND, FixtureHub, two_machine_hub
from hub_mcp import WAIT_SECONDS, start_raw_mcp

from amoeba.wire.times import TICK_BOUND_SECONDS
from hub.sessions_support import (
    POLL_SECONDS,
    RECEIVER,
    SENDER,
    STALE_SECONDS,
    Machines,
    build_machines,
)

#: Past the stale time on the hub's clock, with room for a call.
STALE_WAIT_SECONDS = STALE_SECONDS + 1.0
#: How long to watch for a wake that must not start: several polls.
QUIET_SECONDS = 4 * POLL_SECONDS + 1.0


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[FixtureHub]:
    with two_machine_hub(tmp_path) as running:
        yield running


def _confirmed(world: Machines) -> bool:
    return any(s["push_confirmed_at"] is not None for s in world.sessions(world.alpha))


def test_an_unconfirmed_session_lists_as_such_and_starts_its_machines_work(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub, wake=True)

    async def scenario() -> None:
        async with world.beta.mcp(world.receiver_repo) as run:
            await run.wait_for_presence(SECOND)
            await run.wait_for("the row", lambda: bool(world.sessions(world.alpha)))
            (session,) = world.sessions(world.alpha)
            assert session["push_confirmed_at"] is None
            world.send("r1")
            await run.wait_for("the wake its tick started", world.woke.exists)

    anyio.run(scenario)


def test_a_request_from_alpha_pushes_to_beta_and_a_confirmed_session_holds_off_wakes(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub, wake=True)

    async def scenario() -> None:
        async with world.beta.mcp(world.receiver_repo) as run:
            await run.wait_for_presence(SECOND)
            sent_at = time.monotonic()
            world.send("r1")
            await run.wait_for("the channel event", lambda: bool(run.channel_events))
            assert time.monotonic() - sent_at < POLL_SECONDS + TICK_BOUND_SECONDS
            assert run.channel_events[0].meta["count"] == "1"
            await run.wait_for("the wake of the unconfirmed session", world.woke.exists)

            # The agent answers the event with `inbox`: push is confirmed.
            answer = await run.session.call_tool(
                "inbox", {"directory": str(world.receiver_repo)}
            )
            assert answer.is_error is False, answer.content
            await run.wait_for("push_confirmed_at", lambda: _confirmed(world))

            world.woke.unlink()
            second = world.send("r2")
            assert second["woke"] is None
            assert second["wake_waiting_on"] == []
            await run.wait_for("the second event", lambda: len(run.channel_events) == 2)
            await anyio.sleep(QUIET_SECONDS)
            assert not world.woke.exists()

    anyio.run(scenario)


def test_a_session_on_each_machine_shows_under_its_member_from_either(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub)

    async def scenario() -> None:
        async with world.alpha.mcp(world.sender_repo) as on_alpha:
            async with world.beta.mcp(world.receiver_repo) as on_beta:
                await on_alpha.wait_for_presence(FIRST)
                await on_beta.wait_for_presence(SECOND)
                await on_beta.wait_for(
                    "both rows", lambda: len(world.sessions(world.alpha)) == 2
                )
                for viewer in (world.alpha, world.beta):
                    seen = world.sessions_by_member(viewer)
                    assert {
                        name: [s["machine"] for s in rows]
                        for name, rows in seen.items()
                    } == {
                        SENDER: [FIRST],
                        RECEIVER: [SECOND],
                    }
                    for rows in seen.values():
                        assert all(s["client_version"] for s in rows)
                        assert all(s["behind"] is False for s in rows)

    anyio.run(scenario)


def test_a_killed_session_goes_stale_on_the_hubs_clock_and_the_next_refresh_deletes_it(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub)
    environment = hub.env_for(world.beta.home)
    killed = start_raw_mcp(environment, world.receiver_repo)
    deadline = time.monotonic() + WAIT_SECONDS
    while not world.sessions(world.alpha):
        assert time.monotonic() < deadline, "no row for the first server"
        time.sleep(0.2)
    (dead_row,) = world.session_rows()

    os.kill(killed.pid, signal.SIGKILL)
    killed.wait(timeout=WAIT_SECONDS)
    time.sleep(STALE_WAIT_SECONDS)

    assert world.sessions(world.alpha) == []
    assert world.session_rows() == [dead_row]

    async def refresh() -> None:
        async with world.beta.mcp(world.receiver_repo) as run:
            await run.wait_for(
                "the next refresh to delete the dead row",
                lambda: dead_row not in world.session_rows(),
            )
            assert len(world.session_rows()) == 1

    anyio.run(refresh)


def test_a_clean_exit_deletes_the_row_at_once(hub: FixtureHub) -> None:
    world = build_machines(hub)

    async def scenario() -> None:
        async with world.beta.mcp(world.receiver_repo) as run:
            await run.wait_for("the row", lambda: bool(world.session_rows()))

    anyio.run(scenario)

    assert world.session_rows() == []


def test_an_exit_with_the_hub_stopped_is_bounded_and_the_row_goes_stale(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub)
    left = 0.0

    async def scenario() -> None:
        nonlocal left
        async with world.beta.mcp(world.receiver_repo) as run:
            await run.wait_for("the row", lambda: bool(world.sessions(world.alpha)))
            hub.stop()
            left = time.monotonic()
        left = time.monotonic() - left

    anyio.run(scenario)

    assert left < TICK_BOUND_SECONDS
    hub.start()
    assert len(world.session_rows()) == 1
    time.sleep(STALE_WAIT_SECONDS)
    assert world.sessions(world.alpha) == []
