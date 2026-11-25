"""A session through faults, on real processes (slice 263, 8.3): the hub stopped, its
config broken, a machine removed."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import anyio
import pytest
from hub_fixture import SECOND, FixtureHub, two_machine_hub
from hub_mcp import McpRun, set_hub_timings

from hub.sessions_support import (
    POLL_SECONDS,
    Machines,
    build_machines,
)

BROKEN_CONFIG = "notify_poll_seconds: [not, a, number\n"
TIMING_KEYS = (
    "notify_poll_seconds",
    "session_heartbeat_seconds",
    "session_stale_seconds",
)
#: Several polls: enough ticks to show a run of failures is one line.
SEVERAL_POLLS_SECONDS = 8 * POLL_SECONDS


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[FixtureHub]:
    with two_machine_hub(tmp_path) as running:
        yield running


async def _directory_tool(run: McpRun, world: Machines, tool: str) -> str:
    """The text a tool call returns, which is an error here."""
    result = await run.session.call_tool(tool, {"directory": str(world.receiver_repo)})
    assert result.is_error is True
    (block,) = result.content
    return str(getattr(block, "text", block))


def _warnings(run: McpRun) -> list[str]:
    return [line for line in run.stderr().splitlines() if "WARNING" in line]


def test_with_the_hub_stopped_each_tool_call_names_the_address(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub)

    async def scenario() -> list[str]:
        async with world.beta.mcp(world.receiver_repo) as run:
            await run.wait_for_presence(SECOND)
            hub.stop()
            return [
                await _directory_tool(run, world, tool) for tool in ("list", "inbox")
            ]

    texts = anyio.run(scenario)

    for text in texts:
        assert "HubUnreachableError" in text
        assert hub.address in text


def test_a_broken_hub_config_is_one_warning_and_the_first_tick_after_the_fix_works(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub)
    config = hub.home / "config.yaml"
    good = config.read_text(encoding="utf-8")

    async def scenario() -> None:
        async with world.beta.mcp(world.receiver_repo) as run:
            await run.wait_for_presence(SECOND)
            config.write_text(BROKEN_CONFIG, encoding="utf-8")
            await run.wait_for("a warning", lambda: bool(_warnings(run)))
            await anyio.sleep(SEVERAL_POLLS_SECONDS)
            assert len(_warnings(run)) == 1, run.stderr()

            config.write_text(good, encoding="utf-8")
            await run.wait_for(
                "the recovery line", lambda: bool(run.stderr_lines("recovered"))
            )
            await run.wait_for("the row", lambda: bool(world.sessions(world.alpha)))

    anyio.run(scenario)


def test_a_config_failing_the_third_timing_check_is_refused_naming_the_three_keys(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub)
    # Passes the first two checks (heartbeat >= poll, stale = 2 x heartbeat), not the
    # third (stale >= heartbeat + 2 x poll).
    set_hub_timings(
        hub,
        notify_poll_seconds=2,
        session_heartbeat_seconds=2,
        session_stale_seconds=4,
    )

    done = world.alpha.run("list", "-j")

    assert done.code != 0
    for key in TIMING_KEYS:
        assert key in done.err + done.out, done.err + done.out


def test_rm_machine_with_a_session_open_refuses_its_ticks_until_it_joins_again(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub)

    async def scenario() -> None:
        async with world.beta.mcp(world.receiver_repo) as run:
            await run.wait_for_presence(SECOND)
            removed = hub.run_in(hub.home, "hub", "rm-machine", SECOND)
            assert removed.code == 0, removed.err
            await run.wait_for(
                "a refused tick", lambda: bool(run.stderr_lines("bad_token"))
            )
            text = await _directory_tool(run, world, "list")
            assert f"amoeba hub invite {SECOND}" in text
            assert "amoeba join" in text

            joined = world.beta.run("join", hub.invite(SECOND), "-j")
            assert joined.code == 0, joined.err
            # The removal took the machine's checkouts: its repo is added again.
            added = world.beta.run_in(world.receiver_repo, "add", "-j")
            assert added.code == 0, added.err + added.out
            await run.wait_for(
                "the next tick to succeed", lambda: bool(world.session_rows())
            )
            await run.wait_for(
                "the recovery line", lambda: bool(run.stderr_lines("recovered"))
            )

    anyio.run(scenario)
