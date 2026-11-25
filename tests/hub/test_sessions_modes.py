"""A session across joins and leaves, and the inbox resource (slice 263, 8.5, D2, D4,
D10), on real processes: a real hub, ``amoeba-mcp`` over stdio, the real CLI."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import anyio
import mcp_types as types
import pytest
from hub_clients import install_client_tools
from hub_fixture import SECOND, ClientHome, FixtureHub, two_machine_hub
from hub_mcp import McpRun
from mcp.shared.exceptions import MCPError
from user_configs import example_config_text

from hub.sessions_support import (
    RECEIVER,
    RECEIVER_ORIGIN,
    Machines,
    build_machines,
)

INBOX = "amoeba://inbox"
NEW_MACHINE = "gamma"
NO_MEMBER = "this server serves no member"


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[FixtureHub]:
    with two_machine_hub(tmp_path) as running:
        yield running


async def _read(run: McpRun) -> dict[str, object]:
    result = await run.session.read_resource(INBOX)
    (block,) = result.contents
    assert isinstance(block, types.TextResourceContents)
    document: dict[str, object] = json.loads(block.text)
    return document


async def _until_read(run: McpRun) -> dict[str, object]:
    """The resource once a tick has had a reply (a read before that is an error)."""
    found: list[dict[str, object]] = []

    async def attempt() -> bool:
        try:
            found.append(await _read(run))
        except MCPError:
            return False
        return True

    for _ in range(100):
        if await attempt():
            return found[0]
        await anyio.sleep(0.2)
    raise AssertionError(f"no read succeeded\n{run.stderr()}")


def test_the_resource_reads_from_the_newest_tick_with_no_hub_call(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub)

    async def scenario() -> None:
        async with world.beta.mcp(world.receiver_repo) as run:
            await run.wait_for_presence(SECOND)
            first = await _until_read(run)
            assert set(first) == {"member", "as_of_seq"}
            hub.stop()
            assert await _read(run) == first

    anyio.run(scenario)


def test_before_a_reply_a_read_names_the_ticks_error_and_the_resource_is_still_listed(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub)
    hub.stop()

    async def scenario() -> None:
        async with world.beta.mcp(world.receiver_repo) as run:
            listed = await run.session.list_resources()
            assert [str(resource.uri) for resource in listed.resources] == [INBOX]
            for attempt in (_read, _subscribe):
                with pytest.raises(MCPError, match="HubUnreachableError"):
                    await attempt(run)
            hub.start()
            assert set(await _until_read(run)) == {"member", "as_of_seq"}
            await _subscribe(run)

    anyio.run(scenario)


async def _subscribe(run: McpRun) -> None:
    # The SDK deprecates the call; the server's subscribe is what is under test.
    await run.session.subscribe_resource(INBOX)  # pyright: ignore[reportDeprecated]


def test_a_session_with_no_member_lists_the_resource_and_subscribes_once_it_has_one(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub)
    repo = world.beta.clone(
        "later", "https://github.com/org/later", "cf-later", "later"
    )

    async def scenario() -> None:
        async with world.beta.mcp(repo) as run:
            await run.wait_for("a tick that found no member", lambda: _ticked(run))
            listed = await run.session.list_resources()
            assert [str(resource.uri) for resource in listed.resources] == [INBOX]
            with pytest.raises(MCPError, match=NO_MEMBER):
                await _subscribe(run)

            added = world.beta.run_in(repo, "add", "--program", "shared", "-j")
            assert added.code == 0, added.err + added.out
            await run.wait_for_presence(SECOND)
            # No reconnect: the same session subscribes at a later tick.
            await _subscribed(run)

    anyio.run(scenario)


def _ticked(run: McpRun) -> bool:
    return "presence for" not in run.stderr()


async def _subscribed(run: McpRun) -> None:
    for _ in range(100):
        try:
            await _subscribe(run)
        except MCPError:
            await anyio.sleep(0.2)
        else:
            return
    raise AssertionError(f"never subscribed\n{run.stderr()}")


def _third_machine(hub: FixtureHub) -> tuple[ClientHome, Path, str]:
    """``gamma``: a home that has not joined, with a repo added to its local store."""
    line = hub.invite(NEW_MACHINE)
    home = hub.root / f"client-{NEW_MACHINE}"
    home.mkdir()
    install_client_tools(home)
    (home / "config.yaml").write_text(example_config_text(), encoding="utf-8")
    client = ClientHome(NEW_MACHINE, home, hub)
    repo = client.clone(RECEIVER, RECEIVER_ORIGIN, "cf-gamma", RECEIVER)
    added = client.run_in(repo, "add", "--program", "shared", "-j")
    assert added.code == 0, added.err + added.out
    return client, repo, line


def test_a_session_open_across_join_set_aside_local_moves_to_the_hub_with_no_event(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub)
    gamma, repo, line = _third_machine(hub)

    async def scenario() -> None:
        async with gamma.mcp(repo) as run:
            await run.wait_for_presence("local")
            joined = gamma.run("join", line, "--set-aside-local", "-j")
            assert joined.code == 0, joined.err + joined.out
            added = gamma.run_in(repo, "add", "--program", "shared", "-j")
            assert added.code == 0, added.err + added.out
            await run.wait_for(
                "the session on the hub",
                lambda: any(
                    s["machine"] == NEW_MACHINE for s in world.sessions(world.alpha)
                ),
            )
            assert run.channel_events == []

    anyio.run(scenario)


def test_after_leave_a_plain_join_is_refused_naming_the_flag_and_the_flag_works(
    hub: FixtureHub,
) -> None:
    world = build_machines(hub)

    async def scenario() -> None:
        async with world.beta.mcp(world.receiver_repo) as run:
            await run.wait_for_presence(SECOND)
            left = world.beta.run("leave", "-j")
            assert left.code == 0, left.err + left.out
            # The next tick runs on the local store, which creates it.
            await run.wait_for("a local tick", lambda: _local_store(world).exists())

            plain = world.beta.run("join", hub.invite(SECOND), "-j")
            assert plain.code != 0
            assert "--set-aside-local" in plain.err + plain.out

            flagged = world.beta.run(
                "join", hub.invite(SECOND), "--set-aside-local", "-j"
            )
            assert flagged.code == 0, flagged.err + flagged.out
            added = world.beta.run_in(world.receiver_repo, "add", "-j")
            assert added.code == 0, added.err + added.out
            await run.wait_for(
                "the session on the hub",
                lambda: any(
                    s["machine"] == SECOND for s in world.sessions(world.alpha)
                ),
            )

    anyio.run(scenario)


def _local_store(world: Machines) -> Path:
    return world.beta.home / "amoeba.sqlite3"
