"""Presence: member resolution, the client name and the heartbeat (slice 241, 6.3, 6.4).

A fake clock gives the times written; real sleeps are a few milliseconds, so a loop
turns many times in a test.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import anyio
import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, fake_cf_run
from store_open import open_local_store

from amoeba.mcp.presence import (
    PUSH_ANSWER_SECONDS,
    UNRECOGNIZED_CLIENT,
    PresenceDeps,
    PresenceState,
    client_name,
    heartbeat_loop,
    note_event_attempted,
    note_inbox_called,
    resolve_presence,
)
from amoeba.operations.errors import ContextForgeError
from amoeba.store.checkouts import delete_checkouts_of_member
from amoeba.store.errors import StoreBusyError, StoreCorruptError
from amoeba.store.sessions import prune_stale_sessions
from amoeba.upstream.context_forge.cli_call import CfRun
from mcp_server.presence_rig import (
    FAST,
    MEMBER_ID,
    FakeClock,
    Opener,
    all_session_rows,
    eventually,
    make_deps,
    member_state,
    sessions_in,
    timed_out_cf,
)

CLIENT = "claude-code"


# --- resolution (6.1) --------------------------------------------------------


def test_a_member_directory_sets_the_member(store_path: Path) -> None:
    clock = FakeClock()
    state = PresenceState(started_at=clock())

    anyio.run(resolve_presence, state, make_deps(Opener(store_path), clock))

    assert state.member_id == MEMBER_ID
    assert state.off_reason is None
    assert state.resolved.is_set()


def test_a_non_member_directory_is_off_with_one_info_line(
    store_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    clock = FakeClock()
    state = PresenceState(started_at=clock())
    deps = make_deps(Opener(store_path), clock, cf_run=fake_cf_run(OUTSIDE_ANY_PROJECT))

    with caplog.at_level(logging.INFO):
        anyio.run(resolve_presence, state, deps)

    assert state.member_id is None
    assert state.off_reason is not None and "is not a member" in state.off_reason
    assert state.resolved.is_set()
    lines = [r for r in caplog.records if "is not a member" in r.getMessage()]
    assert [r.levelno for r in lines] == [logging.INFO]


def test_a_member_with_no_checkout_here_is_a_non_member_in_the_log_line(
    store_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with open_local_store(store_path) as store, store.write() as transaction:
        delete_checkouts_of_member(transaction, MEMBER_ID)
    clock = FakeClock()
    state = PresenceState(started_at=clock())

    with caplog.at_level(logging.INFO):
        anyio.run(resolve_presence, state, make_deps(Opener(store_path), clock))

    assert state.member_id is None
    assert state.off_reason is not None and "is not a member" in state.off_reason
    assert any("NotInProgram" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(
    "cf_run", [fake_cf_run(None), timed_out_cf], ids=["cf-fails", "cf-times-out"]
)
def test_a_cf_failure_or_timeout_raises_and_still_ends_pending(
    store_path: Path, cf_run: CfRun
) -> None:
    clock = FakeClock()
    state = PresenceState(started_at=clock())
    deps = make_deps(Opener(store_path), clock, cf_run=cf_run)

    with pytest.raises(ContextForgeError):
        anyio.run(resolve_presence, state, deps)

    assert state.resolved.is_set()
    assert state.member_id is None


def test_cancellation_at_the_lookup_ends_pending_with_no_off_reason(
    store_path: Path,
) -> None:
    clock = FakeClock()
    state = PresenceState(started_at=clock())
    deps = make_deps(Opener(store_path), clock)

    async def run() -> None:
        with anyio.CancelScope() as scope:
            scope.cancel()
            await resolve_presence(state, deps)

    anyio.run(run)

    assert state.resolved.is_set()
    assert state.off_reason is None


# --- client name (6.2) ---------------------------------------------------------


def test_a_displayable_client_name_is_kept() -> None:
    assert client_name(CLIENT) == CLIENT


@pytest.mark.parametrize("name", [None, "", "x" * 65, "bad\nname", "<script>"])
def test_any_other_name_is_the_placeholder_with_a_warning(
    name: str | None, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        assert client_name(name) == UNRECOGNIZED_CLIENT

    assert [r.levelno for r in caplog.records] == [logging.WARNING]


# --- heartbeat (6.2) -----------------------------------------------------------


async def _beat_until(
    state: PresenceState,
    deps: PresenceDeps,
    done: Callable[[], bool],
    client: str = CLIENT,
) -> None:
    """Run the heartbeat until ``done()`` holds, then cancel it."""
    async with anyio.create_task_group() as group:
        group.start_soon(heartbeat_loop, state, deps, client)
        await eventually(done, "the heartbeat reached the expected state")
        group.cancel_scope.cancel()


def test_the_first_beat_writes_the_row_with_the_client_name(
    store_path: Path, tmp_path: Path
) -> None:
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    deps = make_deps(Opener(store_path), clock)

    anyio.run(_beat_until, state, deps, lambda: bool(all_session_rows(store_path)))

    (session,) = sessions_in(store_path, clock(), FAST.session_stale_seconds)
    assert session.session_id == state.session_id
    assert session.member_id == MEMBER_ID
    assert session.client == CLIENT
    assert session.directory == str(tmp_path)
    assert session.started_at == session.heartbeat_at == clock()
    assert session.push_confirmed_at is None


def test_a_bad_client_name_is_stored_as_the_placeholder(
    store_path: Path, tmp_path: Path
) -> None:
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    deps = make_deps(Opener(store_path), clock)

    anyio.run(
        _beat_until,
        state,
        deps,
        lambda: bool(all_session_rows(store_path)),
        client_name("bad\x00name"),
    )

    (row,) = all_session_rows(store_path)
    assert row[1] == UNRECOGNIZED_CLIENT


def test_a_busy_store_is_retried_and_warned_once_per_run(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    busy: list[Exception | None] = [
        StoreBusyError("database is locked") for _ in range(3)
    ]
    opener = Opener(store_path, errors=busy)
    deps = make_deps(opener, clock)

    with caplog.at_level(logging.WARNING):
        anyio.run(_beat_until, state, deps, lambda: bool(all_session_rows(store_path)))

    assert opener.opens >= 4
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "store busy" in warnings[0].getMessage()


def test_a_corrupt_store_propagates_out_of_the_heartbeat(
    store_path: Path, tmp_path: Path
) -> None:
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    opener = Opener(store_path, errors=[StoreCorruptError("file is not a database")])

    with pytest.raises(StoreCorruptError):
        anyio.run(heartbeat_loop, state, make_deps(opener, clock), CLIENT)


def test_a_process_suspended_past_the_stale_limit_gets_its_row_back(
    store_path: Path, tmp_path: Path
) -> None:
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    deps = make_deps(Opener(store_path), clock)
    started = clock()

    async def scenario() -> None:
        async with anyio.create_task_group() as group:
            group.start_soon(heartbeat_loop, state, deps, CLIENT)
            await eventually(lambda: bool(all_session_rows(store_path)), "first beat")
            # The process sleeps; another server's beat prunes its row meanwhile.
            woke = started + timedelta(seconds=FAST.session_stale_seconds + 30)
            with open_local_store(store_path) as other, other.write() as transaction:
                prune_stale_sessions(transaction, woke, FAST.session_stale_seconds)
            assert all_session_rows(store_path) == []
            clock.now = woke
            await eventually(lambda: bool(all_session_rows(store_path)), "re-created")
            group.cancel_scope.cancel()

    anyio.run(scenario)

    (session,) = sessions_in(store_path, clock(), FAST.session_stale_seconds)
    assert session.started_at == started
    assert session.heartbeat_at == clock()


# --- push confirmation (6.4) ---------------------------------------------------


def _state() -> tuple[PresenceState, FakeClock]:
    clock = FakeClock()

    async def build() -> PresenceState:
        return PresenceState(started_at=clock())

    return anyio.run(build), clock


def test_an_inbox_call_within_the_limit_confirms_and_the_next_beat_writes_it(
    store_path: Path, tmp_path: Path
) -> None:
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    note_event_attempted(state, clock())
    clock.advance(PUSH_ANSWER_SECONDS)

    note_inbox_called(state, clock())

    assert state.push_confirmed_at == clock()
    assert state.attempt_at is None
    deps = make_deps(Opener(store_path), clock)
    confirmed = lambda: any(row[4] for row in all_session_rows(store_path))  # noqa: E731
    anyio.run(_beat_until, state, deps, confirmed)
    (session,) = sessions_in(store_path, clock(), FAST.session_stale_seconds)
    assert session.push_confirmed_at == clock()


@pytest.mark.parametrize("attempted", [False, True], ids=["no-attempt", "too-late"])
def test_an_inbox_call_with_no_attempt_or_after_the_limit_does_not_confirm(
    attempted: bool,
) -> None:
    state, clock = _state()
    if attempted:
        note_event_attempted(state, clock())
        clock.advance(PUSH_ANSWER_SECONDS + 1)

    note_inbox_called(state, clock())

    assert state.push_confirmed_at is None
    assert state.attempt_at is None


def test_a_second_event_while_one_waits_does_not_reset_it() -> None:
    state, clock = _state()
    first = clock()
    note_event_attempted(state, first)
    clock.advance(PUSH_ANSWER_SECONDS - 1)

    note_event_attempted(state, clock())

    assert state.attempt_at == first


def test_an_unanswered_attempt_past_the_limit_is_replaced_by_the_next() -> None:
    state, clock = _state()
    note_event_attempted(state, clock())
    clock.advance(PUSH_ANSWER_SECONDS + 1)

    note_event_attempted(state, clock())

    assert state.attempt_at == clock()


def test_confirmation_is_sticky() -> None:
    state, clock = _state()
    note_event_attempted(state, clock())
    note_inbox_called(state, clock())
    confirmed = state.push_confirmed_at
    clock.advance(PUSH_ANSWER_SECONDS * 10)

    note_inbox_called(state, clock())

    assert confirmed is not None
    assert state.push_confirmed_at == confirmed
