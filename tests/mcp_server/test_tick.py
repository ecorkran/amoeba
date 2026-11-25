"""The session tick: events and baselines (slice 263, D1, D4)."""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import anyio
import pytest
from store.message_support import send_request
from store_open import open_local_store

from amoeba.mcp.after_runner import AfterRunner
from amoeba.mcp.channel_event import CHANNEL_METHOD
from amoeba.mcp.inbox_resource import INBOX_URI, RESOURCE_UPDATED_METHOD
from amoeba.mcp.presence import (
    PresenceDeps,
)
from amoeba.mcp.tick import run_ticks
from amoeba.store.deliveries import write_delivery
from amoeba.store.row_values import encode_timestamp
from amoeba.store.vocabulary import DeliveryEvent, MessageKind
from amoeba.wiring_presence import LastReply, SessionIdentity
from mcp_server.presence_rig import (
    MEMBER_ID,
    PEER,
    START,
    RecordingOutbound,
    deliver,
    eventually,
    make_connection,
)
from mcp_server.tick_rig import (
    CLIENT,
    MARKER,
    QUIET_SECONDS,
    events_of,
    no_spawn,
    replied,
    run_tick,
    setup,
)

# --- baselines and events ------------------------------------------------------


def test_mail_already_waiting_is_not_pushed_and_new_mail_is(
    store_path: Path, tmp_path: Path
) -> None:
    deliver(store_path, DeliveryEvent.SENT)
    state, deps, opener = setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 3, "the baseline and a tick")
        await anyio.sleep(QUIET_SECONDS)
        assert events_of(outbound) == []
        deliver(store_path, DeliveryEvent.CANCELLED)
        await eventually(lambda: bool(events_of(outbound)), "one event")

    anyio.run(run_tick, deps, state, outbound, scenario)

    (event,) = events_of(outbound)
    assert event["meta"] == {"first_seq": "2", "last_seq": "2", "count": "1"}


def test_two_deliveries_in_one_tick_are_one_event_announced_once(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, opener = setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(replied(state), "the baseline")
        deliver(store_path, DeliveryEvent.SENT, DeliveryEvent.CANCELLED)
        await eventually(lambda: bool(events_of(outbound)), "one event")
        await eventually(lambda: opener.opens >= 6, "ticks after the rise")

    anyio.run(run_tick, deps, state, outbound, scenario)

    (event,) = events_of(outbound)
    assert event["meta"] == {"first_seq": "1", "last_seq": "2", "count": "2"}


def test_no_delivery_sends_nothing(store_path: Path, tmp_path: Path) -> None:
    state, deps, opener = setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 5, "several ticks")

    anyio.run(run_tick, deps, state, outbound, scenario)

    assert outbound.sent == []


def test_a_highest_number_below_the_last_one_takes_a_new_baseline_and_sends_nothing(
    store_path: Path, tmp_path: Path
) -> None:
    deliver(store_path, DeliveryEvent.SENT)
    state, deps, _ = setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(replied(state), "the baseline")
        state.last_seen = 50
        await eventually(lambda: state.last_seen == 1, "the new baseline")
        await anyio.sleep(QUIET_SECONDS)
        assert events_of(outbound) == []
        deliver(store_path, DeliveryEvent.CANCELLED)
        await eventually(lambda: bool(events_of(outbound)), "an event above it")

    anyio.run(run_tick, deps, state, outbound, scenario)


def test_a_changed_way_takes_a_new_baseline_and_sends_nothing(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(replied(state), "the baseline")
        way = state.way
        state.way = "another-way"
        deliver(store_path, DeliveryEvent.SENT)
        await eventually(lambda: state.way == way, "the way back to this one")
        await anyio.sleep(QUIET_SECONDS)
        assert events_of(outbound) == []
        assert state.last_seen == 1
        deliver(store_path, DeliveryEvent.CANCELLED)
        await eventually(lambda: bool(events_of(outbound)), "an event after it")

    anyio.run(run_tick, deps, state, outbound, scenario)


def test_two_ticks_never_overlap(store_path: Path, tmp_path: Path) -> None:
    state, deps, _ = setup(store_path, tmp_path)
    inner = deps.open_steps
    seen = {"active": 0, "most": 0, "opens": 0}

    @contextmanager
    def probe(last: LastReply, identity: SessionIdentity | None) -> Generator[Any]:
        seen["active"] += 1
        seen["opens"] += 1
        seen["most"] = max(seen["most"], seen["active"])
        try:
            with inner(last, identity) as steps:
                yield steps
        finally:
            seen["active"] -= 1

    probed = PresenceDeps(probe, deps.cf_run, deps.clock, deps.after_deps)

    async def scenario() -> None:
        await eventually(lambda: seen["opens"] >= 6, "several ticks")

    anyio.run(run_tick, probed, state, RecordingOutbound(), scenario)

    assert seen["most"] == 1


def test_a_note_pushes_naming_its_kind_and_sender(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    def deliver_note() -> None:
        # The table's note shape written directly; ``test_note_push`` sends notes
        # through the real writers.
        stamp = encode_timestamp(START)
        with open_local_store(store_path) as store, store.write() as transaction:
            transaction.execute(
                "INSERT INTO messages (message_id, kind, from_member, to_member, "
                "depth, subject, body, created_at, state_changed_at, owner_id) "
                "VALUES ('n1', ?, ?, ?, 1, 's', 'b', ?, ?, "
                "(SELECT owner_id FROM owners))",
                (MessageKind.NOTE.value, PEER, MEMBER_ID, stamp, stamp),
            )
            write_delivery(transaction, MEMBER_ID, "n1", DeliveryEvent.SENT, START)

    async def scenario() -> None:
        await eventually(replied(state), "the baseline")
        deliver_note()
        await eventually(lambda: bool(events_of(outbound)), "the note's event")

    anyio.run(run_tick, deps, state, outbound, scenario)

    (event,) = events_of(outbound)
    assert f"note, sent from {PEER}" in str(event["content"])


@pytest.mark.parametrize(
    "closed", [anyio.ClosedResourceError, anyio.BrokenResourceError]
)
def test_a_notify_on_a_closed_stream_is_dropped_not_raised(
    store_path: Path, tmp_path: Path, closed: type[Exception]
) -> None:
    state, deps, _ = setup(store_path, tmp_path)
    outbound = RecordingOutbound(error=closed())

    async def scenario() -> None:
        await eventually(replied(state), "the baseline")
        deliver(store_path, DeliveryEvent.SENT)
        await eventually(lambda: state.attempt_at is not None, "the attempt recorded")

    anyio.run(run_tick, deps, state, outbound, scenario)

    assert outbound.sent == []


def test_any_other_notify_failure_raises_out_of_the_loop(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = setup(store_path, tmp_path)
    outbound = RecordingOutbound(error=RuntimeError("encoder broke"))

    async def run() -> None:
        async with anyio.create_task_group() as group:
            runner = AfterRunner(deps, no_spawn)
            group.start_soon(
                run_ticks, make_connection(outbound), state, deps, CLIENT, runner
            )
            await eventually(replied(state), "the baseline")
            deliver(store_path, DeliveryEvent.SENT)

    with pytest.raises(BaseExceptionGroup) as raised:
        anyio.run(run)

    assert raised.group_contains(RuntimeError, match="encoder broke")


def test_the_info_line_has_the_numbers_and_no_message_text(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    state, deps, _ = setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(replied(state), "the baseline")
        with open_local_store(store_path) as store, store.write() as transaction:
            send_request(transaction, MARKER, from_member=PEER, to_member=MEMBER_ID)
            transaction.execute(
                "UPDATE messages SET subject = ?, body = ? WHERE message_id = ?",
                (MARKER, MARKER, MARKER),
            )
            write_delivery(transaction, MEMBER_ID, MARKER, DeliveryEvent.SENT, START)
        await eventually(lambda: bool(events_of(outbound)), "the event")

    with caplog.at_level(logging.INFO):
        anyio.run(run_tick, deps, state, outbound, scenario)

    (line,) = [
        r.getMessage() for r in caplog.records if "channel event" in r.getMessage()
    ]
    assert line == "channel event attempted: first_seq=1 last_seq=1 count=1"
    assert MARKER not in " ".join(r.getMessage() for r in caplog.records)
    assert MARKER not in str(events_of(outbound))


def test_a_subscribed_client_also_gets_the_resource_update(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = setup(store_path, tmp_path)
    state.subscribed = True
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(replied(state), "the baseline")
        deliver(store_path, DeliveryEvent.SENT)
        await eventually(lambda: len(outbound.sent) == 2, "both notifications")

    anyio.run(run_tick, deps, state, outbound, scenario)

    assert outbound.methods() == [CHANNEL_METHOD, RESOURCE_UPDATED_METHOD]
    assert outbound.sent[1][1] == {"uri": INBOX_URI}


def test_the_presence_line_names_the_member_the_client_and_the_machine(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    state, deps, _ = setup(store_path, tmp_path)

    async def scenario() -> None:
        await eventually(replied(state), "the first reply")

    with caplog.at_level(logging.INFO):
        anyio.run(run_tick, deps, state, RecordingOutbound(), scenario)

    (line,) = [
        r.getMessage() for r in caplog.records if "presence for" in r.getMessage()
    ]
    assert line.startswith(f"presence for {MEMBER_ID}: protocol ")
    assert line.endswith(f", client {CLIENT}, machine local")
