"""The ``amoeba://inbox`` resource over an SDK client (slice 241, D5, 8.2)."""

from __future__ import annotations

import json
import logging
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
from amoeba.wiring_presence import StoreOpener
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
    resource_opener: StoreOpener | None = None,
) -> None:
    async def main() -> None:
        state = PresenceState(started_at=clock())
        server: Server[Any] = Server("inbox-test")
        register_inbox_resource(server, state, resource_opener or deps.open_store)
        with anyio.fail_after(15):
            async with serving(
                server, presence_background(state, deps), received
            ) as session:
                await test(session, state)

    anyio.run(main)


def test_a_list_made_while_resolving_waits_then_gets_the_answer(
    store_path: Path,
) -> None:
    clock = FakeClock()
    block = threading.Event()
    deps = make_deps(Opener(store_path, block=block), clock)

    async def test(session: ClientSession, state: PresenceState) -> None:
        answers: list[types.ListResourcesResult] = []

        async def ask() -> None:
            answers.append(await session.list_resources())

        async with anyio.create_task_group() as group:
            group.start_soon(ask)
            await anyio.sleep(0.2)
            assert answers == [] and not state.resolved.is_set()
            block.set()
        (answer,) = answers
        assert [str(r.uri) for r in answer.resources] == [INBOX_URI]

    _run(deps, clock, test)


def test_a_non_member_lists_nothing_and_every_other_method_is_invalid(
    store_path: Path,
) -> None:
    clock = FakeClock()
    deps = make_deps(Opener(store_path), clock, cf_run=fake_cf_run(OUTSIDE_ANY_PROJECT))

    async def test(session: ClientSession, state: PresenceState) -> None:
        assert (await session.list_resources()).resources == []
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


def test_a_store_error_in_read_fails_only_that_request(
    store_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    clock = FakeClock()
    deps = make_deps(Opener(store_path), clock)
    resource_opener = Opener(store_path, errors=[StoreBusyError("database is locked")])

    async def test(session: ClientSession, state: PresenceState) -> None:
        with pytest.raises(MCPError) as raised:
            await session.read_resource(INBOX_URI)
        assert raised.value.error.code == types.INTERNAL_ERROR
        assert "StoreBusyError" in raised.value.error.message
        assert (await session.read_resource(INBOX_URI)).contents

    with caplog.at_level(logging.ERROR):
        _run(deps, clock, test, resource_opener=resource_opener)

    (record,) = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert record.exc_info is not None
    assert "inbox resource read failed" in record.getMessage()


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
        await eventually(lambda: opener.opens >= 4, "the watcher's baseline")
        deliver(store_path)
        await eventually(lambda: state.attempt_at is not None, "the channel event")
        await anyio.sleep(0.2)

    _run(deps, clock, test, received)

    assert (RESOURCE_UPDATED_METHOD in received.methods()) is updated
