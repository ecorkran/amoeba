"""Push and presence against a real interactive Claude Code session (slice 241, D10).

Three sessions run in turn, each in its own world: push reaches the agent and the
session confirms; a killed server's session goes stale; a non-member directory gets
tools and no session. Spend is pre-authorized for live tiers.
"""

from __future__ import annotations

from pathlib import Path

from mcp_types.version import HANDSHAKE_PROTOCOL_VERSIONS

from live.channels.harness import (
    INBOX_CALL_WAIT_SECONDS,
    PROMPTED_CALL_WAIT_SECONDS,
    STALE_MARGIN_SECONDS,
    STARTUP_SCREEN_WAIT_SECONDS,
)
from live.channels.world import (
    FORGE,
    TIMINGS,
    ChannelWorld,
    all_sessions,
    session_in,
    sessions_of,
    wait_for_log,
    wait_until,
)
from live.pause.harness import run_amoeba

HEARTBEAT_WAIT = TIMINGS["session_heartbeat_seconds"] + STALE_MARGIN_SECONDS
STALE_WAIT = TIMINGS["session_stale_seconds"] + STALE_MARGIN_SECONDS
PRESENCE_LINE = "presence for "


def _same_place(a: str, b: Path) -> bool:
    return Path(a).resolve() == b.resolve()


def test_the_store_amoeba_resolves_is_under_the_throwaway_home(
    channel_world: ChannelWorld, tmp_path: Path
) -> None:
    home = Path(channel_world.forge.environ["AMOEBA_HOME"]).resolve()
    live_home = (Path.home() / ".local" / "state" / "amoeba").resolve()

    assert channel_world.forge.store.resolve().parent == home
    assert channel_world.forge.store.exists()
    assert home != live_home
    assert not home.is_relative_to(live_home)
    # The throwaway home belongs to this pytest run.
    assert home.is_relative_to(tmp_path.resolve().parent)


def test_session_one_push_reaches_the_agent_and_confirms(
    channel_world: ChannelWorld,
) -> None:
    forge = channel_world.forge.repo
    session, log, _ = session_in(channel_world, forge, "session-one")
    session.start()
    try:
        wait_until(
            session,
            lambda: any(
                _same_place(s["directory"], forge)
                for s in sessions_of(channel_world, FORGE)
            ),
            "a live session under cf-s",
            STARTUP_SCREEN_WAIT_SECONDS,
        )
        presence = wait_for_log(
            session, log, PRESENCE_LINE, STARTUP_SCREEN_WAIT_SECONDS
        )
        version = presence.split("protocol ", 1)[1].split(",", 1)[0]
        assert version in HANDSHAKE_PROTOCOL_VERSIONS

        sent = run_amoeba(
            channel_world.squadron,
            "send",
            "--to",
            FORGE,
            "--id",
            "sq-1",
            "--subject",
            "Need X",
            "--body",
            "Please add X",
        )
        assert sent.returncode == 0, sent.stderr + sent.stdout

        wait_for_log(session, log, "tool inbox called", INBOX_CALL_WAIT_SECONDS)
        wait_until(
            session,
            lambda: any(
                s["push_confirmed_at"] for s in sessions_of(channel_world, FORGE)
            ),
            "push_confirmed_at in list -j",
            HEARTBEAT_WAIT,
        )
    finally:
        session.terminate()
    # The server deletes its row once stdin closes; staleness is the bounded fallback.
    wait_until(
        session,
        lambda: sessions_of(channel_world, FORGE) == [],
        "no session after a clean exit",
        STALE_WAIT,
    )


def test_killed_server_goes_stale(channel_world: ChannelWorld) -> None:
    forge = channel_world.forge.repo
    session, _, pid_file = session_in(channel_world, forge, "killed")
    session.start()
    try:
        wait_until(
            session,
            lambda: bool(sessions_of(channel_world, FORGE)),
            "a live session under cf-s",
            STARTUP_SCREEN_WAIT_SECONDS,
        )
        session.kill_server(pid_file)
        wait_until(
            session,
            lambda: not sessions_of(channel_world, FORGE),
            "the killed server's session to read as gone",
            STALE_WAIT,
        )
    finally:
        session.terminate()


def test_session_three_a_non_member_directory_serves_tools_and_no_session(
    channel_world: ChannelWorld,
) -> None:
    session, log, _ = session_in(channel_world, channel_world.outside, "outside")
    session.start()
    try:
        wait_for_log(session, log, "is not a member", STARTUP_SCREEN_WAIT_SECONDS)
        assert all_sessions(channel_world) == []
        session.type_prompt(
            "Call the list tool of the amoeba MCP server once, then stop."
        )
        wait_for_log(session, log, "tool list called", PROMPTED_CALL_WAIT_SECONDS)
    finally:
        session.terminate()
    assert all_sessions(channel_world) == []
