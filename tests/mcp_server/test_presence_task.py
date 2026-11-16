"""``run_presence``: its top-level handler and clean exit (slice 241, D2, D6, 6.5)."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

import anyio
import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, fake_cf_run

from amoeba.mcp.presence import PresenceDeps, PresenceState
from amoeba.mcp.presence_task import run_presence
from amoeba.store.errors import StoreBusyError, StoreCorruptError
from amoeba.upstream.context_forge.cli_call import CfRun
from mcp_server.presence_rig import (
    FAST,
    FakeClock,
    Opener,
    RecordingOutbound,
    all_session_rows,
    eventually,
    make_connection,
    make_deps,
    sessions_in,
    timed_out_cf,
)


async def _run_to_end(deps: PresenceDeps, clock: FakeClock) -> PresenceState:
    """Run presence on an initialized connection until it returns by itself."""
    state = PresenceState(started_at=clock())
    connection = make_connection(RecordingOutbound())
    connection.initialized.set()
    with anyio.fail_after(10):
        await run_presence(connection, state, deps)
    return state


def _exception_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.levelno == logging.ERROR and record.exc_info is not None
    ]


@pytest.mark.parametrize(
    ("cf_run", "errors"),
    [
        (fake_cf_run(None), []),
        (timed_out_cf, []),
        (None, [StoreCorruptError("file is not a database")]),
    ],
    ids=["cf-fails", "cf-times-out", "store-error-in-lookup"],
)
def test_a_failed_lookup_writes_no_row_logs_the_traceback_and_returns(
    store_path: Path,
    caplog: pytest.LogCaptureFixture,
    cf_run: CfRun | None,
    errors: list[Exception | None],
) -> None:
    clock = FakeClock()
    deps = make_deps(Opener(store_path, errors=list(errors)), clock, cf_run=cf_run)

    with caplog.at_level(logging.INFO):
        state = anyio.run(_run_to_end, deps, clock)

    assert all_session_rows(store_path) == []
    assert state.member_id is None and state.resolved.is_set()
    messages = [record.getMessage() for record in _exception_records(caplog)]
    assert "no presence: the member lookup failed" in messages


def test_a_non_member_returns_with_no_row(store_path: Path) -> None:
    clock = FakeClock()
    deps = make_deps(Opener(store_path), clock, cf_run=fake_cf_run(OUTSIDE_ANY_PROJECT))

    state = anyio.run(_run_to_end, deps, clock)

    assert all_session_rows(store_path) == []
    assert state.off_reason is not None


def test_a_corrupt_store_in_the_heartbeat_ends_presence_and_deletes_the_row(
    store_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    clock = FakeClock()
    # Lookup, first beat, then a corrupt store at the second beat.
    errors: list[Exception | None] = [None, None, StoreCorruptError("malformed")]
    deps = make_deps(Opener(store_path, errors=errors), clock)

    with caplog.at_level(logging.INFO):
        anyio.run(_run_to_end, deps, clock)

    assert all_session_rows(store_path) == []
    (record,) = _exception_records(caplog)
    assert "presence stopped" in record.getMessage()


def test_a_clean_exit_deletes_the_row(store_path: Path) -> None:
    clock = FakeClock()
    deps = make_deps(Opener(store_path), clock)

    async def scenario() -> None:
        state = PresenceState(started_at=clock())
        connection = make_connection(RecordingOutbound())
        connection.initialized.set()
        async with anyio.create_task_group() as group:
            group.start_soon(run_presence, connection, state, deps)
            await eventually(lambda: bool(all_session_rows(store_path)), "a row")
            group.cancel_scope.cancel()

    anyio.run(scenario)

    assert all_session_rows(store_path) == []


def test_a_failed_delete_leaves_a_row_that_stops_counting_after_the_limit(
    store_path: Path,
) -> None:
    clock = FakeClock()
    opener = Opener(store_path)
    deps = make_deps(opener, clock)

    async def scenario() -> None:
        state = PresenceState(started_at=clock())
        connection = make_connection(RecordingOutbound())
        connection.initialized.set()
        async with anyio.create_task_group() as group:
            group.start_soon(run_presence, connection, state, deps)
            await eventually(lambda: bool(all_session_rows(store_path)), "a row")
            # Every open from now on, the exit delete's included, finds it busy.
            opener.errors.extend(StoreBusyError("locked") for _ in range(100))
            group.cancel_scope.cancel()

    anyio.run(scenario)

    assert len(all_session_rows(store_path)) == 1
    stale = FAST.session_stale_seconds
    assert len(sessions_in(store_path, clock(), stale)) == 1
    assert sessions_in(store_path, clock() + timedelta(seconds=stale), stale) == ()
