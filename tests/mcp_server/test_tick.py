"""The session tick (slice 263, D1, D3, D4; ports 241's push and heartbeat tests).

The tick runs on a real SDK ``Connection`` whose outbound records what is sent, with
``LocalSteps`` on a throwaway store. A fake clock gives the hub's times; the sleeps
are a few milliseconds, so the loop turns many times in a test.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Awaitable, Callable, Generator, Sequence
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

import anyio
import pytest
from cf_fixtures import DEFAULT_WORKTREE, OUTSIDE_ANY_PROJECT, fake_cf_run
from store.message_support import send_request
from store_open import open_local_store

from amoeba.client.errors import (
    ClientFileError,
    HubRefusedError,
    HubUnreachableError,
)
from amoeba.config.user_config import ConfigError
from amoeba.mcp import tick as tick_module
from amoeba.mcp.after_runner import AfterRunner
from amoeba.mcp.channel_event import CHANNEL_METHOD
from amoeba.mcp.inbox_resource import INBOX_URI, RESOURCE_UPDATED_METHOD
from amoeba.mcp.presence import (
    UNRECOGNIZED_CLIENT,
    PresenceDeps,
    PresenceState,
    client_name,
)
from amoeba.mcp.tick import CF_REASK_SECONDS, run_ticks
from amoeba.store.checkouts import delete_checkouts_of_member
from amoeba.store.deliveries import write_delivery
from amoeba.store.errors import StoreBusyError, StoreCorruptError
from amoeba.store.row_values import encode_timestamp
from amoeba.store.vocabulary import DeliveryEvent, MessageKind
from amoeba.upstream.context_forge.cli_call import CfRun
from amoeba.wire.protocol import RefusalCode
from amoeba.wiring_presence import LastReply
from mcp_server.presence_rig import (
    FAST,
    MEMBER_ID,
    PEER,
    START,
    FakeClock,
    Opener,
    RecordingOutbound,
    all_session_rows,
    deliver,
    eventually,
    make_connection,
    make_deps,
    member_state,
    sessions_in,
    timed_out_cf,
)

CLIENT = "claude-code"
#: The constant as the program has it, before the fixture makes it short.
BEFORE_FIRST_REPLY = tick_module.TICK_SECONDS_BEFORE_FIRST_REPLY
#: Planted in a message's text; must never reach the log or the event.
MARKER = "MARKER-TEXT-7f"
#: Ticks a test lets pass to be sure nothing was sent.
QUIET_SECONDS = 0.15


@pytest.fixture(autouse=True)
def short_wait_before_the_first_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real wait is five seconds; a failing tick here retries in milliseconds."""
    monkeypatch.setattr(tick_module, "TICK_SECONDS_BEFORE_FIRST_REPLY", 0.01)


def _no_spawn(work: Callable[[], Awaitable[None]]) -> None:
    """A runner that never starts an after-step: the tests here are about the tick."""


async def _tick(
    deps: PresenceDeps,
    state: PresenceState,
    outbound: RecordingOutbound,
    scenario: Callable[[], Awaitable[None]],
    client: str = CLIENT,
) -> None:
    """Run the tick while ``scenario`` (async) drives it, then cancel it."""
    connection = make_connection(outbound)
    runner = AfterRunner(deps, _no_spawn)
    async with anyio.create_task_group() as group:
        group.start_soon(run_ticks, connection, state, deps, client, runner)
        await scenario()
        group.cancel_scope.cancel()


def _events(outbound: RecordingOutbound) -> list[dict[str, Any]]:
    return [params for method, params in outbound.sent if method == CHANNEL_METHOD]


def _setup(
    store_path: Path,
    tmp_path: Path,
    errors: Sequence[Exception | None] = (),
    cf_run: CfRun | None = None,
) -> tuple[PresenceState, PresenceDeps, Opener]:
    clock = FakeClock()
    opener = Opener(store_path, errors=list(errors))
    return (
        member_state(clock, tmp_path),
        make_deps(opener, clock, cf_run=cf_run),
        opener,
    )


def _replied(state: PresenceState) -> Callable[[], bool]:
    return lambda: state.as_of_seq is not None


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


# --- baselines and events ------------------------------------------------------


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

    anyio.run(_tick, deps, state, outbound, scenario)

    (event,) = _events(outbound)
    assert event["meta"] == {"first_seq": "2", "last_seq": "2", "count": "1"}


def test_two_deliveries_in_one_tick_are_one_event_announced_once(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, opener = _setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(_replied(state), "the baseline")
        deliver(store_path, DeliveryEvent.SENT, DeliveryEvent.CANCELLED)
        await eventually(lambda: bool(_events(outbound)), "one event")
        await eventually(lambda: opener.opens >= 6, "ticks after the rise")

    anyio.run(_tick, deps, state, outbound, scenario)

    (event,) = _events(outbound)
    assert event["meta"] == {"first_seq": "1", "last_seq": "2", "count": "2"}


def test_no_delivery_sends_nothing(store_path: Path, tmp_path: Path) -> None:
    state, deps, opener = _setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 5, "several ticks")

    anyio.run(_tick, deps, state, outbound, scenario)

    assert outbound.sent == []


def test_a_highest_number_below_the_last_one_takes_a_new_baseline_and_sends_nothing(
    store_path: Path, tmp_path: Path
) -> None:
    deliver(store_path, DeliveryEvent.SENT)
    state, deps, _ = _setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(_replied(state), "the baseline")
        state.last_seen = 50
        await eventually(lambda: state.last_seen == 1, "the new baseline")
        await anyio.sleep(QUIET_SECONDS)
        assert _events(outbound) == []
        deliver(store_path, DeliveryEvent.CANCELLED)
        await eventually(lambda: bool(_events(outbound)), "an event above it")

    anyio.run(_tick, deps, state, outbound, scenario)


def test_a_changed_way_takes_a_new_baseline_and_sends_nothing(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = _setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(_replied(state), "the baseline")
        way = state.way
        state.way = "another-way"
        deliver(store_path, DeliveryEvent.SENT)
        await eventually(lambda: state.way == way, "the way back to this one")
        await anyio.sleep(QUIET_SECONDS)
        assert _events(outbound) == []
        assert state.last_seen == 1
        deliver(store_path, DeliveryEvent.CANCELLED)
        await eventually(lambda: bool(_events(outbound)), "an event after it")

    anyio.run(_tick, deps, state, outbound, scenario)


def test_two_ticks_never_overlap(store_path: Path, tmp_path: Path) -> None:
    state, deps, _ = _setup(store_path, tmp_path)
    inner = deps.open_steps
    seen = {"active": 0, "most": 0, "opens": 0}

    @contextmanager
    def probe(last: LastReply) -> Generator[Any]:
        seen["active"] += 1
        seen["opens"] += 1
        seen["most"] = max(seen["most"], seen["active"])
        try:
            with inner(last) as steps:
                yield steps
        finally:
            seen["active"] -= 1

    probed = PresenceDeps(probe, deps.cf_run, deps.clock, deps.after_deps)

    async def scenario() -> None:
        await eventually(lambda: seen["opens"] >= 6, "several ticks")

    anyio.run(_tick, probed, state, RecordingOutbound(), scenario)

    assert seen["most"] == 1


def test_a_note_pushes_naming_its_kind_and_sender(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = _setup(store_path, tmp_path)
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
        await eventually(_replied(state), "the baseline")
        deliver_note()
        await eventually(lambda: bool(_events(outbound)), "the note's event")

    anyio.run(_tick, deps, state, outbound, scenario)

    (event,) = _events(outbound)
    assert f"note, sent from {PEER}" in str(event["content"])


@pytest.mark.parametrize(
    "closed", [anyio.ClosedResourceError, anyio.BrokenResourceError]
)
def test_a_notify_on_a_closed_stream_is_dropped_not_raised(
    store_path: Path, tmp_path: Path, closed: type[Exception]
) -> None:
    state, deps, _ = _setup(store_path, tmp_path)
    outbound = RecordingOutbound(error=closed())

    async def scenario() -> None:
        await eventually(_replied(state), "the baseline")
        deliver(store_path, DeliveryEvent.SENT)
        await eventually(lambda: state.attempt_at is not None, "the attempt recorded")

    anyio.run(_tick, deps, state, outbound, scenario)

    assert outbound.sent == []


def test_any_other_notify_failure_raises_out_of_the_loop(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = _setup(store_path, tmp_path)
    outbound = RecordingOutbound(error=RuntimeError("encoder broke"))

    async def run() -> None:
        async with anyio.create_task_group() as group:
            runner = AfterRunner(deps, _no_spawn)
            group.start_soon(
                run_ticks, make_connection(outbound), state, deps, CLIENT, runner
            )
            await eventually(_replied(state), "the baseline")
            deliver(store_path, DeliveryEvent.SENT)

    with pytest.raises(BaseExceptionGroup) as raised:
        anyio.run(run)

    assert raised.group_contains(RuntimeError, match="encoder broke")


def test_the_info_line_has_the_numbers_and_no_message_text(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    state, deps, _ = _setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(_replied(state), "the baseline")
        with open_local_store(store_path) as store, store.write() as transaction:
            send_request(transaction, MARKER, from_member=PEER, to_member=MEMBER_ID)
            transaction.execute(
                "UPDATE messages SET subject = ?, body = ? WHERE message_id = ?",
                (MARKER, MARKER, MARKER),
            )
            write_delivery(transaction, MEMBER_ID, MARKER, DeliveryEvent.SENT, START)
        await eventually(lambda: bool(_events(outbound)), "the event")

    with caplog.at_level(logging.INFO):
        anyio.run(_tick, deps, state, outbound, scenario)

    (line,) = [
        r.getMessage() for r in caplog.records if "channel event" in r.getMessage()
    ]
    assert line == "channel event attempted: first_seq=1 last_seq=1 count=1"
    assert MARKER not in " ".join(r.getMessage() for r in caplog.records)
    assert MARKER not in str(_events(outbound))


def test_a_subscribed_client_also_gets_the_resource_update(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = _setup(store_path, tmp_path)
    state.subscribed = True
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(_replied(state), "the baseline")
        deliver(store_path, DeliveryEvent.SENT)
        await eventually(lambda: len(outbound.sent) == 2, "both notifications")

    anyio.run(_tick, deps, state, outbound, scenario)

    assert outbound.methods() == [CHANNEL_METHOD, RESOURCE_UPDATED_METHOD]
    assert outbound.sent[1][1] == {"uri": INBOX_URI}


def test_the_presence_line_names_the_member_the_client_and_the_machine(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    state, deps, _ = _setup(store_path, tmp_path)

    async def scenario() -> None:
        await eventually(_replied(state), "the first reply")

    with caplog.at_level(logging.INFO):
        anyio.run(_tick, deps, state, RecordingOutbound(), scenario)

    (line,) = [
        r.getMessage() for r in caplog.records if "presence for" in r.getMessage()
    ]
    assert line.startswith(f"presence for {MEMBER_ID}: protocol ")
    assert line.endswith(f", client {CLIENT}, machine local")


# --- failures (D4) ---------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        StoreBusyError("database is locked"),
        StoreCorruptError("file is not a database"),
        ConfigError("config.yaml is missing"),
        ClientFileError("client.yaml is gone"),
        HubUnreachableError("no reply"),
        HubRefusedError("refused", RefusalCode.HUB_ERROR),
    ],
    ids=lambda error: type(error).__name__,
)
def test_each_operational_failure_skips_the_tick_with_one_warning_per_run(
    store_path: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    state, deps, opener = _setup(store_path, tmp_path, [error] * 3)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(_replied(state), "a tick that succeeds")
        assert state.resolved.is_set()

    with caplog.at_level(logging.INFO):
        anyio.run(_tick, deps, state, outbound, scenario)

    failures = [m for m in _warnings(caplog) if m.startswith("tick failed:")]
    assert failures == [f"tick failed: {type(error).__name__}: {error}"]
    recovered = [r for r in caplog.records if r.getMessage() == "tick recovered"]
    assert [r.levelno for r in recovered] == [logging.INFO]
    assert opener.opens >= 4
    assert state.last_error is None
    assert state.member_id == MEMBER_ID


def test_busy_ticks_are_skipped_and_the_next_event_is_sent(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, opener = _setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(_replied(state), "the baseline")
        opener.errors.extend(StoreBusyError("locked") for _ in range(3))
        deliver(store_path, DeliveryEvent.SENT)
        await eventually(lambda: bool(_events(outbound)), "the event after them")

    anyio.run(_tick, deps, state, outbound, scenario)

    assert len(_events(outbound)) == 1


def test_mail_waiting_before_the_first_successful_tick_is_not_pushed(
    store_path: Path, tmp_path: Path
) -> None:
    busy = [StoreBusyError("locked") for _ in range(4)]
    state, deps, opener = _setup(store_path, tmp_path, busy)
    deliver(store_path, DeliveryEvent.SENT)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 7, "the baseline, then ticks")

    anyio.run(_tick, deps, state, outbound, scenario)

    assert outbound.sent == []


def test_a_new_error_type_in_a_run_warns_again(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    errors = [
        StoreBusyError("locked"),
        StoreBusyError("locked"),
        HubUnreachableError("no reply"),
    ]
    state, deps, _ = _setup(store_path, tmp_path, errors)

    async def scenario() -> None:
        await eventually(_replied(state), "a tick that succeeds")

    with caplog.at_level(logging.INFO):
        anyio.run(_tick, deps, state, RecordingOutbound(), scenario)

    assert len([m for m in _warnings(caplog) if "tick failed" in m]) == 2


def test_a_failing_tick_resolves_presence_and_keeps_its_error(
    store_path: Path, tmp_path: Path
) -> None:
    blocked = [StoreBusyError("locked")] * 1000
    state, deps, opener = _setup(store_path, tmp_path, blocked)

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 3, "ticks that fail")
        assert state.resolved.is_set()
        assert state.as_of_seq is None
        assert state.last_error == "StoreBusyError: locked"

    anyio.run(_tick, deps, state, RecordingOutbound(), scenario)


def test_a_bug_in_a_tick_raises_out_of_the_loop(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = _setup(store_path, tmp_path, [RuntimeError("a bug")])

    async def run() -> None:
        runner = AfterRunner(deps, _no_spawn)
        await run_ticks(
            make_connection(RecordingOutbound()), state, deps, CLIENT, runner
        )

    with pytest.raises(RuntimeError, match="a bug"):
        anyio.run(run)


def test_the_wait_is_five_seconds_before_a_reply_and_the_replys_after(
    store_path: Path, tmp_path: Path
) -> None:
    state, _, _ = _setup(store_path, tmp_path)
    assert BEFORE_FIRST_REPLY == 5
    assert tick_module._interval(state) == 0.01  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001

    state.poll_seconds = 7.5

    assert tick_module._interval(state) == 7.5  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001


# --- the member lookup (D3) ------------------------------------------------------


class CountingCf:
    """A ``cf`` that answers with ``fixture`` (swappable), fails the first
    ``failures`` calls, and counts its calls."""

    def __init__(self, fixture: str | None, failures: int = 0) -> None:
        self.fixture = fixture
        self.failures = failures
        self.calls = 0

    def __call__(
        self, argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls += 1
        if self.calls <= self.failures:
            return fake_cf_run(None)(argv, **kwargs)
        return fake_cf_run(self.fixture)(argv, **kwargs)


def test_a_cf_that_fails_twice_then_answers_gives_a_row_at_the_third_tick(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cf = CountingCf(DEFAULT_WORKTREE, failures=2)
    state, deps, _ = _setup(store_path, tmp_path, cf_run=cf)

    async def scenario() -> None:
        await eventually(lambda: bool(all_session_rows(store_path)), "the row")

    with caplog.at_level(logging.INFO):
        anyio.run(_tick, deps, state, RecordingOutbound(), scenario)

    assert cf.calls == 3
    assert len([m for m in _warnings(caplog) if "ContextForgeError" in m]) == 1
    assert any(r.getMessage() == "tick recovered" for r in caplog.records)


def test_a_cf_that_hangs_ends_each_tick_with_one_warning(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[int] = []

    def hanging(argv: Sequence[str], **kwargs: object) -> Any:
        calls.append(1)
        return timed_out_cf(argv, **kwargs)

    state, deps, _ = _setup(store_path, tmp_path, cf_run=hanging)

    async def scenario() -> None:
        await eventually(lambda: len(calls) >= 4, "several ticks")

    with caplog.at_level(logging.WARNING):
        anyio.run(_tick, deps, state, RecordingOutbound(), scenario)

    assert len([m for m in _warnings(caplog) if "tick failed" in m]) == 1
    assert state.resolved.is_set()
    assert all_session_rows(store_path) == []


def test_a_directory_that_is_not_a_project_asks_cf_once_per_reask_time(
    store_path: Path, tmp_path: Path
) -> None:
    cf = CountingCf(OUTSIDE_ANY_PROJECT)
    clock = FakeClock()
    opener = Opener(store_path)
    state = member_state(clock, tmp_path)
    deps = make_deps(opener, clock, cf_run=cf)

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 4, "ticks that do not ask again")
        assert cf.calls == 1
        assert state.member_id is None
        assert state.off_reason
        clock.advance(CF_REASK_SECONDS)
        await eventually(lambda: cf.calls == 2, "the ask once it is that old")

    anyio.run(_tick, deps, state, RecordingOutbound(), scenario)

    assert all_session_rows(store_path) == []


def test_after_add_the_row_appears_within_the_reask_time_and_after_rm_the_row_goes(
    store_path: Path, tmp_path: Path
) -> None:
    cf = CountingCf(OUTSIDE_ANY_PROJECT)
    clock = FakeClock()
    opener = Opener(store_path)
    state = member_state(clock, tmp_path)
    deps = make_deps(opener, clock, cf_run=cf)

    async def scenario() -> None:
        await eventually(lambda: cf.calls == 1, "the first ask")
        cf.fixture = DEFAULT_WORKTREE
        clock.advance(CF_REASK_SECONDS)
        await eventually(lambda: bool(all_session_rows(store_path)), "the row")
        with open_local_store(store_path) as store, store.write() as transaction:
            delete_checkouts_of_member(transaction, MEMBER_ID)
        await eventually(lambda: not all_session_rows(store_path), "the row removed")
        await eventually(lambda: state.member_id is None, "the member gone")

    anyio.run(_tick, deps, state, RecordingOutbound(), scenario)


def test_a_repo_not_added_yet_is_a_tick_with_no_member_and_no_row(
    store_path: Path, tmp_path: Path
) -> None:
    with open_local_store(store_path) as store, store.write() as transaction:
        delete_checkouts_of_member(transaction, MEMBER_ID)
    state, deps, _ = _setup(store_path, tmp_path)

    async def scenario() -> None:
        await eventually(_replied(state), "a reply")

    anyio.run(_tick, deps, state, RecordingOutbound(), scenario)

    assert state.member_id is None
    assert state.off_reason is not None
    assert all_session_rows(store_path) == []


# --- the row the tick keeps (D2, D5) ---------------------------------------------


def test_the_first_tick_writes_the_row_with_the_client_name(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = _setup(store_path, tmp_path)

    async def scenario() -> None:
        await eventually(lambda: bool(all_session_rows(store_path)), "the row")

    anyio.run(_tick, deps, state, RecordingOutbound(), scenario)

    (session,) = sessions_in(store_path, deps.clock(), FAST.session_stale_seconds)
    assert session.session_id == state.session_id
    assert session.member_id == MEMBER_ID
    assert session.client == CLIENT
    assert session.directory == str(tmp_path)
    assert session.started_at == session.heartbeat_at == deps.clock()
    assert session.push_confirmed_at is None


def test_a_bad_client_name_is_stored_as_the_placeholder(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = _setup(store_path, tmp_path)

    async def scenario() -> None:
        await eventually(lambda: bool(all_session_rows(store_path)), "the row")

    anyio.run(
        _tick, deps, state, RecordingOutbound(), scenario, client_name("bad\x00name")
    )

    (row,) = all_session_rows(store_path)
    assert row[1] == UNRECOGNIZED_CLIENT


def test_a_process_suspended_past_the_stale_limit_gets_its_row_back(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = _setup(store_path, tmp_path)
    clock = FakeClock()
    deps = make_deps(Opener(store_path), clock)
    started = clock()

    async def scenario() -> None:
        await eventually(lambda: bool(all_session_rows(store_path)), "first row")
        woke = started + timedelta(seconds=FAST.session_stale_seconds + 30)
        clock.now = woke
        await eventually(
            lambda: (
                [row[3] for row in all_session_rows(store_path)]
                == [encode_timestamp(woke)]
            ),
            "the row written again at the hub's time",
        )

    anyio.run(_tick, deps, state, RecordingOutbound(), scenario)

    (session,) = sessions_in(store_path, clock(), FAST.session_stale_seconds)
    assert session.started_at == session.heartbeat_at == clock()


def test_a_push_confirmation_reaches_the_row_at_the_next_tick(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = _setup(store_path, tmp_path)

    async def scenario() -> None:
        await eventually(lambda: bool(all_session_rows(store_path)), "the row")
        state.push_confirmed_at = deps.clock()
        await eventually(
            lambda: any(row[4] for row in all_session_rows(store_path)),
            "the confirmation written",
        )

    anyio.run(_tick, deps, state, RecordingOutbound(), scenario)

    (session,) = sessions_in(store_path, deps.clock(), FAST.session_stale_seconds)
    assert session.push_confirmed_at == deps.clock()
