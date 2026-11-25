"""The ``amoeba://inbox`` resource over an SDK client (slice 241, D5, 8.2)."""

from __future__ import annotations

import json
import threading
from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import Any

import anyio
import mcp_types as types
import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, fake_cf_run
from mcp import ClientSession
from mcp.server import Server
from mcp.shared.exceptions import MCPError
from store_open import open_local_store

from amoeba.mcp import tick as tick_module
from amoeba.mcp.inbox_resource import (
    AS_OF_SEQ_FIELD,
    INBOX_URI,
    MEMBER_FIELD,
    RESOURCE_UPDATED_METHOD,
    register_inbox_resource,
)
from amoeba.mcp.presence import PresenceDeps, PresenceState
from amoeba.store.deliveries import highest_assigned_seq
from amoeba.store.errors import StoreBusyError
from mcp_server.presence_rig import (
    MEMBER_ID,
    FakeClock,
    Opener,
    deliver,
    eventually,
    make_deps,
)
from mcp_server.serving_rig import (
    Received,
    presence_background,
    serving,
    subscribe,
    unsubscribe,
)

FOREIGN_URI = "amoeba://outbox"


def _run(
    deps: PresenceDeps,
    clock: FakeClock,
    test: Callable[[ClientSession, PresenceState], Awaitable[None]],
    received: Received | None = None,
) -> None:
    async def main() -> None:
        state = PresenceState(started_at=clock())
        server: Server[Any] = Server("inbox-test")
        register_inbox_resource(server, state)
        with anyio.fail_after(15):
            async with serving(
                server, presence_background(state, deps), received
            ) as session:
                await test(session, state)

    anyio.run(main)


def test_a_list_made_while_the_first_tick_is_stuck_gets_the_resource_at_once(
    store_path: Path,
) -> None:
    clock = FakeClock()
    block = threading.Event()
    deps = make_deps(Opener(store_path, block=block), clock)

    async def test(session: ClientSession, state: PresenceState) -> None:
        try:
            with anyio.fail_after(2):
                answer = await session.list_resources()
            assert not state.resolved.is_set()
            assert [str(r.uri) for r in answer.resources] == [INBOX_URI]
        finally:
            block.set()

    _run(deps, clock, test)


def test_a_non_member_lists_the_resource_and_every_other_method_is_invalid(
    store_path: Path,
) -> None:
    clock = FakeClock()
    deps = make_deps(Opener(store_path), clock, cf_run=fake_cf_run(OUTSIDE_ANY_PROJECT))

    async def test(session: ClientSession, state: PresenceState) -> None:
        listed = (await session.list_resources()).resources
        assert [str(r.uri) for r in listed] == [INBOX_URI]
        for call in (
            session.read_resource,
            partial(subscribe, session),
            partial(unsubscribe, session),
        ):
            with pytest.raises(MCPError) as raised:
                await call(INBOX_URI)
            assert raised.value.error.code == types.INVALID_PARAMS

    _run(deps, clock, test)


def test_read_gives_the_member_and_the_number_inbox_reports(store_path: Path) -> None:
    deliver(store_path)
    clock = FakeClock()
    deps = make_deps(Opener(store_path), clock)

    async def test(session: ClientSession, state: PresenceState) -> None:
        listed = (await session.list_resources()).resources
        assert [str(r.uri) for r in listed] == [INBOX_URI]
        result = await session.read_resource(INBOX_URI)
        (contents,) = result.contents
        assert isinstance(contents, types.TextResourceContents)
        document = json.loads(contents.text)
        # ``inbox`` reports ``highest_assigned_seq`` as its ``as_of_seq``.
        with open_local_store(store_path) as store, store.read() as transaction:
            reported = highest_assigned_seq(transaction)
        assert reported == 1
        assert document == {MEMBER_FIELD: MEMBER_ID, AS_OF_SEQ_FIELD: reported}

    _run(deps, clock, test)


def test_subscribe_and_unsubscribe_toggle_the_flag_and_unsubscribe_twice_is_fine(
    store_path: Path,
) -> None:
    clock = FakeClock()
    deps = make_deps(Opener(store_path), clock)

    async def test(session: ClientSession, state: PresenceState) -> None:
        await subscribe(session, INBOX_URI)
        assert state.subscribed
        await unsubscribe(session, INBOX_URI)
        assert not state.subscribed
        await unsubscribe(session, INBOX_URI)
        assert not state.subscribed

    _run(deps, clock, test)


def test_a_foreign_uri_is_invalid_for_a_member(store_path: Path) -> None:
    clock = FakeClock()
    deps = make_deps(Opener(store_path), clock)

    async def test(session: ClientSession, state: PresenceState) -> None:
        for call in (
            session.read_resource,
            partial(subscribe, session),
            partial(unsubscribe, session),
        ):
            with pytest.raises(MCPError) as raised:
                await call(FOREIGN_URI)
            assert raised.value.error.code == types.INVALID_PARAMS

    _run(deps, clock, test)


def test_before_a_first_reply_a_read_or_subscribe_fails_with_the_ticks_last_error(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tick_module, "TICK_SECONDS_BEFORE_FIRST_REPLY", 0.01)
    clock = FakeClock()
    busy: list[Exception | None] = [StoreBusyError("database is locked")] * 10_000
    deps = make_deps(Opener(store_path, errors=busy), clock)

    async def test(session: ClientSession, state: PresenceState) -> None:
        listed = (await session.list_resources()).resources
        assert [str(r.uri) for r in listed] == [INBOX_URI]
        for call in (
            session.read_resource,
            partial(subscribe, session),
            partial(unsubscribe, session),
        ):
            with pytest.raises(MCPError) as raised:
                await call(INBOX_URI)
            assert raised.value.error.code == types.INTERNAL_ERROR
            assert "StoreBusyError: database is locked" in raised.value.error.message

    _run(deps, clock, test)


@pytest.mark.parametrize(
    ("steps", "updated"),
    [(("subscribe",), True), ((), False), (("subscribe", "unsubscribe"), False)],
    ids=["subscribed", "never-subscribed", "unsubscribed"],
)
def test_only_a_subscribed_client_gets_the_resource_update(
    store_path: Path, steps: tuple[str, ...], updated: bool
) -> None:
    clock = FakeClock()
    opener = Opener(store_path)
    deps = make_deps(opener, clock)
    received = Received()

    async def test(session: ClientSession, state: PresenceState) -> None:
        for step in steps:
            await (subscribe if step == "subscribe" else unsubscribe)(
                session, INBOX_URI
            )
        await eventually(lambda: state.as_of_seq is not None, "the baseline tick")
        deliver(store_path)
        await eventually(lambda: state.attempt_at is not None, "the channel event")
        await anyio.sleep(0.2)

    _run(deps, clock, test, received)

    assert (RESOURCE_UPDATED_METHOD in received.methods()) is updated
