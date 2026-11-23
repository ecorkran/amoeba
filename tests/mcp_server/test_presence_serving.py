"""``amoeba-mcp``'s server with presence, in process (slice 241, D1 to D6, 9.2).

The real ``build_server`` behind ``serve_pinned``, an SDK client over memory streams,
a fake ``cf`` on ``PATH`` for the tools and an injected one for presence.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path

import anyio
import mcp_types as types
import pytest
from cf_fixtures import (
    DEFAULT_WORKTREE,
    OUTSIDE_ANY_PROJECT,
    fake_cf_run,
    write_fake_cf_with_projects,
)
from cli.cli_support import write_config
from mcp import ClientSession

from amoeba.mcp.channel_event import CHANNEL_CAPABILITY
from amoeba.mcp.presence import PresenceDeps, PresenceState, ToolPresence
from amoeba.mcp.server import build_server
from amoeba.store.errors import StoreCorruptError
from amoeba.upstream.context_forge.cli_call import CfRun
from mcp_server.presence_rig import (
    MEMBER_ID,
    PEER,
    FakeClock,
    Opener,
    all_session_rows,
    deliver,
    eventually,
    make_deps,
    seed_member,
)
from mcp_server.serving_rig import presence_background, serving

#: The bound the design sets on any answer while presence is stuck.
ANSWER_SECONDS = 1.0


@pytest.fixture
def store_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The ``AMOEBA_HOME`` store with this repo registered, and a fake ``cf`` first on
    ``PATH`` for the tools, which run ``cf`` in this process."""
    bin_dir = tmp_path / "bin"
    write_fake_cf_with_projects(bin_dir, DEFAULT_WORKTREE)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    write_config()
    path = Path(os.environ["AMOEBA_HOME"]) / "amoeba.sqlite3"
    seed_member(path, MEMBER_ID)
    seed_member(path, PEER)
    return path


def _serve(
    deps: PresenceDeps,
    clock: FakeClock,
    test: Callable[[ClientSession, PresenceState], Awaitable[None]],
) -> None:
    async def main() -> None:
        state = PresenceState(started_at=clock())
        server = build_server(ToolPresence(state, clock), deps.open_store)
        with anyio.fail_after(20):
            async with serving(server, presence_background(state, deps)) as session:
                await test(session, state)

    anyio.run(main)


async def _capabilities(session: ClientSession) -> types.ServerCapabilities:
    return (await session.initialize()).capabilities


def _assert_declares_push(capabilities: types.ServerCapabilities) -> None:
    assert capabilities.experimental == {CHANNEL_CAPABILITY: {}}
    assert capabilities.resources is not None
    assert capabilities.resources.subscribe is True


@pytest.mark.parametrize(
    ("cf_run", "logged", "level"),
    [
        (fake_cf_run(OUTSIDE_ANY_PROJECT), "is not a member", logging.INFO),
        (fake_cf_run(None), "presence stopped", logging.ERROR),
    ],
    ids=["non-member", "cf-fails"],
)
def test_a_server_with_no_member_declares_push_serves_tools_and_does_nothing_else(
    store_path: Path,
    caplog: pytest.LogCaptureFixture,
    cf_run: CfRun,
    logged: str,
    level: int,
) -> None:
    clock = FakeClock()
    opener = Opener(store_path)
    deps = make_deps(opener, clock, cf_run=cf_run)

    async def test(session: ClientSession, state: PresenceState) -> None:
        _assert_declares_push(await _capabilities(session))
        await state.resolved.wait()
        assert (await session.list_tools()).tools
        decided = await session.call_tool("decisions", {})
        assert decided.is_error is False
        assert (await session.list_resources()).resources == []
        opens = opener.opens
        await anyio.sleep(0.2)
        assert opener.opens == opens, "no loop runs"

    with caplog.at_level(logging.INFO):
        _serve(deps, clock, test)

    assert all_session_rows(store_path) == []
    (record,) = [r for r in caplog.records if logged in r.getMessage()]
    assert record.levelno == level


def test_a_member_server_writes_a_row_and_an_inbox_call_after_an_event_confirms(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    clock = FakeClock()
    opener = Opener(store_path)
    deps = make_deps(opener, clock)

    async def test(session: ClientSession, state: PresenceState) -> None:
        _assert_declares_push(await _capabilities(session))
        await eventually(lambda: bool(all_session_rows(store_path)), "the session row")
        # The lookup, a beat and the watcher's baseline have all opened the store.
        await eventually(lambda: opener.opens >= 4, "the watcher's baseline")
        deliver(store_path)
        await eventually(lambda: state.attempt_at is not None, "the channel event")
        result = await session.call_tool("inbox", {"directory": str(tmp_path)})
        assert result.is_error is False
        assert state.push_confirmed_at is not None
        await eventually(
            lambda: any(row[4] for row in all_session_rows(store_path)),
            "push_confirmed_at written by the next beat",
        )

    with caplog.at_level(logging.INFO):
        _serve(deps, clock, test)

    lines = [record.getMessage() for record in caplog.records]
    assert "tool inbox called" in lines
    assert any(
        line.startswith(f"presence for {MEMBER_ID}: protocol 20") and "client " in line
        for line in lines
    )
    assert all_session_rows(store_path) == [], "the clean exit deletes the row"


def test_a_stuck_store_never_blocks_a_tool_call(store_path: Path) -> None:
    clock = FakeClock()
    block = threading.Event()
    deps = make_deps(Opener(store_path, block=block), clock)

    async def test(session: ClientSession, state: PresenceState) -> None:
        try:
            with anyio.fail_after(ANSWER_SECONDS):
                await session.send_ping()
            with anyio.fail_after(ANSWER_SECONDS):
                await session.list_tools()
            with anyio.fail_after(ANSWER_SECONDS):
                decided = await session.call_tool("decisions", {})
            assert decided.is_error is False
            assert not state.resolved.is_set(), "presence was still stuck"
        finally:
            # The stuck worker must finish before the test's threads are joined.
            block.set()

    _serve(deps, clock, test)


def test_a_watcher_failure_is_logged_deletes_the_row_and_tools_keep_answering(
    store_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    clock = FakeClock()
    opener = Opener(store_path)
    deps = make_deps(opener, clock)

    async def test(session: ClientSession, state: PresenceState) -> None:
        await eventually(lambda: bool(all_session_rows(store_path)), "the first beat")
        opener.errors.extend([StoreCorruptError("malformed"), None])
        await eventually(
            lambda: any("presence stopped" in r.getMessage() for r in caplog.records),
            "presence to stop",
        )
        await eventually(lambda: not all_session_rows(store_path), "the row deleted")
        decided = await session.call_tool("decisions", {})
        assert decided.is_error is False

    with caplog.at_level(logging.INFO):
        _serve(deps, clock, test)

    (record,) = [r for r in caplog.records if "presence stopped" in r.getMessage()]
    assert record.exc_info is not None
