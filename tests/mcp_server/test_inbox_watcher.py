"""The push loop (slice 241, D2, D4, D5, 7.2).

The watcher runs on a real SDK ``Connection`` whose outbound records what is sent,
so ``Connection.notify``'s own handling of a closed stream is what the pin tests
exercise. Intervals are a few milliseconds.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

import anyio
import pytest
from store.message_support import send_request

from amoeba.mcp.channel_event import CHANNEL_METHOD
from amoeba.mcp.inbox_resource import INBOX_URI, RESOURCE_UPDATED_METHOD
from amoeba.mcp.inbox_watcher import watch_inbox
from amoeba.mcp.presence import PresenceDeps, PresenceState
from amoeba.store.deliveries import write_delivery
from amoeba.store.errors import StoreBusyError, StoreCorruptError
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, MessageKind
from mcp_server.presence_rig import (
    MEMBER_ID,
    PEER,
    START,
    FakeClock,
    Opener,
    RecordingOutbound,
    deliver,
    eventually,
    make_connection,
    make_deps,
    member_state,
)

#: Planted in a message's text; must never reach the log or the event.
MARKER = "MARKER-TEXT-7f"
#: Ticks a test lets pass to be sure nothing was sent.
QUIET_SECONDS = 0.15


async def _watch(
    deps: PresenceDeps,
    state: PresenceState,
    outbound: RecordingOutbound,
    scenario: Callable[[], Awaitable[None]],
) -> None:
    """Run the watcher while ``scenario`` (async) drives it, then cancel it."""
    connection = make_connection(outbound)
    async with anyio.create_task_group() as group:
        group.start_soon(watch_inbox, connection, state, deps)
        await scenario()
        group.cancel_scope.cancel()


def _events(outbound: RecordingOutbound) -> list[dict[str, object]]:
    return [params for method, params in outbound.sent if method == CHANNEL_METHOD]


def _setup(
    store_path: Path, tmp_path: Path, errors: list[Exception | None] | None = None
) -> tuple[PresenceState, PresenceDeps, Opener]:
    clock = FakeClock()
    opener = Opener(store_path, errors=errors or [])
    return member_state(clock, tmp_path), make_deps(opener, clock), opener


def test_mail_already_waiting_is_not_pushed_and_new_mail_is(
    store_path: Path, tmp_path: Path
) -> None:
    deliver(store_path, DeliveryEvent.SENT)
    state, deps, opener = _setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 3, "the baseline and a tick")
        await anyio.sleep(QUIET_SECONDS)
        assert _events(outbound) == []
        deliver(store_path, DeliveryEvent.CANCELLED)
        await eventually(lambda: bool(_events(outbound)), "one event")

    anyio.run(_watch, deps, state, outbound, scenario)

    (event,) = _events(outbound)
    assert event["meta"] == {"first_seq": "2", "last_seq": "2", "count": "1"}


def test_two_deliveries_in_one_tick_are_one_event(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, opener = _setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 1, "the baseline")
        deliver(store_path, DeliveryEvent.SENT, DeliveryEvent.CANCELLED)
        await eventually(lambda: bool(_events(outbound)), "one event")
        await anyio.sleep(QUIET_SECONDS)

    anyio.run(_watch, deps, state, outbound, scenario)

    (event,) = _events(outbound)
    assert event["meta"] == {"first_seq": "1", "last_seq": "2", "count": "2"}


def test_a_delivery_between_the_two_reads_is_announced_once(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, opener = _setup(store_path, tmp_path)
    # Open 1 is the baseline, 2 the first tick's high read, 3 its rows read.
    writes = {2: DeliveryEvent.SENT, 3: DeliveryEvent.CANCELLED}
    opener.on_open = lambda number: (
        deliver(store_path, writes[number]) if number in writes else None
    )
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 8, "ticks after the rise")

    anyio.run(_watch, deps, state, outbound, scenario)

    (event,) = _events(outbound)
    assert event["meta"] == {"first_seq": "1", "last_seq": "2", "count": "2"}


def test_no_delivery_sends_nothing(store_path: Path, tmp_path: Path) -> None:
    state, deps, opener = _setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 5, "several ticks")

    anyio.run(_watch, deps, state, outbound, scenario)

    assert outbound.sent == []


def test_a_busy_tick_is_skipped_and_the_next_event_is_sent(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    state, deps, opener = _setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 1, "the baseline")
        opener.errors.extend(StoreBusyError("locked") for _ in range(3))
        deliver(store_path, DeliveryEvent.SENT)
        await eventually(
            lambda: bool(_events(outbound)), "the event after the busy ticks"
        )

    with caplog.at_level(logging.WARNING):
        anyio.run(_watch, deps, state, outbound, scenario)

    assert len(_events(outbound)) == 1
    assert len([r for r in caplog.records if "store busy" in r.getMessage()]) == 1


def test_a_busy_baseline_retries_and_sends_nothing_until_it_succeeds(
    store_path: Path, tmp_path: Path
) -> None:
    busy: list[Exception | None] = [StoreBusyError("locked") for _ in range(4)]
    state, deps, opener = _setup(store_path, tmp_path, busy)
    deliver(store_path, DeliveryEvent.SENT)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 7, "the baseline retried, then ticks")

    anyio.run(_watch, deps, state, outbound, scenario)

    # Mail waiting before the baseline succeeds counts as already there.
    assert outbound.sent == []


def test_any_other_store_error_raises_out_of_the_loop(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = _setup(
        store_path, tmp_path, [None, StoreCorruptError("malformed")]
    )

    async def run() -> None:
        await watch_inbox(make_connection(RecordingOutbound()), state, deps)

    with pytest.raises(StoreCorruptError):
        anyio.run(run)


def test_a_note_pushes_naming_its_kind_and_sender(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, opener = _setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    def deliver_note() -> None:
        # The table's note shape (240's migration allows it). 243 adds the writer,
        # and its push criterion tests this path with notes that writer makes.
        stamp = encode_timestamp(START)
        with Store.open(store_path) as store, store.write() as transaction:
            transaction.execute(
                "INSERT INTO messages (message_id, kind, from_member, to_member, "
                "depth, subject, body, created_at, state_changed_at) "
                "VALUES ('n1', ?, ?, ?, 1, 's', 'b', ?, ?)",
                (MessageKind.NOTE.value, PEER, MEMBER_ID, stamp, stamp),
            )
            write_delivery(transaction, MEMBER_ID, "n1", DeliveryEvent.SENT, START)

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 1, "the baseline")
        deliver_note()
        await eventually(lambda: bool(_events(outbound)), "the note's event")

    anyio.run(_watch, deps, state, outbound, scenario)

    (event,) = _events(outbound)
    assert f"note, sent from {PEER}" in str(event["content"])


@pytest.mark.parametrize(
    "closed", [anyio.ClosedResourceError, anyio.BrokenResourceError]
)
def test_a_notify_on_a_closed_stream_is_dropped_not_raised(
    store_path: Path, tmp_path: Path, closed: type[Exception]
) -> None:
    state, deps, opener = _setup(store_path, tmp_path)
    outbound = RecordingOutbound(error=closed())

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 1, "the baseline")
        deliver(store_path, DeliveryEvent.SENT)
        await eventually(lambda: state.attempt_at is not None, "the attempt recorded")

    anyio.run(_watch, deps, state, outbound, scenario)

    assert outbound.sent == []


def test_any_other_notify_failure_raises_out_of_the_loop(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, opener = _setup(store_path, tmp_path)
    outbound = RecordingOutbound(error=RuntimeError("encoder broke"))

    async def run() -> None:
        async with anyio.create_task_group() as group:
            group.start_soon(watch_inbox, make_connection(outbound), state, deps)
            await eventually(lambda: opener.opens >= 1, "the baseline")
            deliver(store_path, DeliveryEvent.SENT)

    with pytest.raises(BaseExceptionGroup) as raised:
        anyio.run(run)

    assert raised.group_contains(RuntimeError, match="encoder broke")


def test_the_info_line_has_the_numbers_and_no_message_text(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    state, deps, opener = _setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 1, "the baseline")
        with Store.open(store_path) as store, store.write() as transaction:
            send_request(transaction, MARKER, from_member=PEER, to_member=MEMBER_ID)
            transaction.execute(
                "UPDATE messages SET subject = ?, body = ? WHERE message_id = ?",
                (MARKER, MARKER, MARKER),
            )
            write_delivery(transaction, MEMBER_ID, MARKER, DeliveryEvent.SENT, START)
        await eventually(lambda: bool(_events(outbound)), "the event")

    with caplog.at_level(logging.INFO):
        anyio.run(_watch, deps, state, outbound, scenario)

    (line,) = [
        r.getMessage() for r in caplog.records if "channel event" in r.getMessage()
    ]
    assert line == "channel event attempted: first_seq=1 last_seq=1 count=1"
    assert MARKER not in " ".join(r.getMessage() for r in caplog.records)
    assert MARKER not in str(_events(outbound))


def test_a_subscribed_client_also_gets_the_resource_update(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, opener = _setup(store_path, tmp_path)
    state.subscribed = True
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 1, "the baseline")
        deliver(store_path, DeliveryEvent.SENT)
        await eventually(lambda: len(outbound.sent) == 2, "both notifications")

    anyio.run(_watch, deps, state, outbound, scenario)

    assert outbound.methods() == [CHANNEL_METHOD, RESOURCE_UPDATED_METHOD]
    assert outbound.sent[1][1] == {"uri": INBOX_URI}
