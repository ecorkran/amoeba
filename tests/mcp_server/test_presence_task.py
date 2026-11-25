"""``run_presence``: its top-level handler and clean exit (slices 241 D2 and D6, 263
D4 and D8)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import anyio
import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, fake_cf_run

from amoeba.client.errors import (
    ClientFileError,
    HubRefusedError,
    HubUnreachableError,
)
from amoeba.config.user_config import ConfigError
from amoeba.mcp import tick as tick_module
from amoeba.mcp.presence import PresenceDeps, PresenceState
from amoeba.mcp.presence_task import run_presence
from amoeba.store.errors import StoreBusyError
from amoeba.upstream.context_forge.cli_call import CfRun
from amoeba.wire.protocol import RefusalCode
from mcp_server.presence_rig import (
    FAST,
    FakeClock,
    Opener,
    RecordingOutbound,
    all_session_rows,
    eventually,
    make_connection,
    make_deps,
    raise_when_called_from,
    sessions_in,
    timed_out_cf,
)


@pytest.fixture(autouse=True)
def short_wait_before_the_first_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tick_module, "TICK_SECONDS_BEFORE_FIRST_REPLY", 0.01)


async def _run_until(
    deps: PresenceDeps,
    clock: FakeClock,
    condition_name: str,
    condition: Callable[[PresenceState], bool],
) -> PresenceState:
    """Run presence on an initialized connection until ``condition`` holds, then end
    it as the server's close does (a cancel) and let ``run_presence`` finish."""
    state = PresenceState(started_at=clock())
    connection = make_connection(RecordingOutbound())
    connection.initialized.set()
    async with anyio.create_task_group() as group:
        group.start_soon(run_presence, connection, state, deps)
        await eventually(lambda: condition(state), condition_name)
        group.cancel_scope.cancel()
    return state


def _resolved(state: PresenceState) -> bool:
    return state.resolved.is_set()


def _replied(state: PresenceState) -> bool:
    return state.as_of_seq is not None


def _row_in(store_path: Path) -> Callable[[PresenceState], bool]:
    return lambda _state: bool(all_session_rows(store_path))


def _exception_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.levelno == logging.ERROR and record.exc_info is not None
    ]


@pytest.mark.parametrize(
    "cf_run", [fake_cf_run(None), timed_out_cf], ids=["cf-fails", "cf-times-out"]
)
def test_a_failed_lookup_skips_the_tick_and_does_not_end_presence(
    store_path: Path, caplog: pytest.LogCaptureFixture, cf_run: CfRun
) -> None:
    clock = FakeClock()
    deps = make_deps(Opener(store_path), clock, cf_run=cf_run)

    with caplog.at_level(logging.INFO):
        state = anyio.run(
            _run_until,
            deps,
            clock,
            "the first tick to end",
            _resolved,
        )

    assert all_session_rows(store_path) == []
    assert state.member_id is None
    assert state.resolved.is_set()
    assert _exception_records(caplog) == []
    assert any(
        "tick failed: ContextForgeError" in r.getMessage() for r in caplog.records
    )


def test_a_non_member_returns_with_no_row(store_path: Path) -> None:
    clock = FakeClock()
    deps = make_deps(Opener(store_path), clock, cf_run=fake_cf_run(OUTSIDE_ANY_PROJECT))

    state = anyio.run(_run_until, deps, clock, "a reply", _replied)

    assert all_session_rows(store_path) == []
    assert state.told_member is False


def test_a_bug_in_the_tick_ends_presence_and_deletes_the_row(
    store_path: Path, caplog: pytest.LogCaptureFixture
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
            opener.on_open = raise_when_called_from("work", [RuntimeError("a bug")])
            await eventually(
                lambda: any(
                    "presence stopped" in r.getMessage() for r in caplog.records
                ),
                "presence to stop",
            )
            await eventually(lambda: not all_session_rows(store_path), "row deleted")

    with caplog.at_level(logging.INFO):
        anyio.run(scenario)

    (record,) = _exception_records(caplog)
    assert "presence stopped" in record.getMessage()


def test_a_clean_exit_deletes_the_row(store_path: Path) -> None:
    clock = FakeClock()
    deps = make_deps(Opener(store_path), clock)

    anyio.run(
        _run_until,
        deps,
        clock,
        "a row",
        _row_in(store_path),
    )

    assert all_session_rows(store_path) == []


@pytest.mark.parametrize(
    "error",
    [
        HubUnreachableError("no reply"),
        HubRefusedError("refused", RefusalCode.DOOR_VERSION),
        ClientFileError("client.yaml is gone"),
        StoreBusyError("locked"),
        ConfigError("config.yaml is missing"),
    ],
    ids=lambda error: type(error).__name__,
)
def test_an_exit_that_gets_no_reply_returns_in_time_and_raises_nothing(
    store_path: Path, caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    clock = FakeClock()
    opener = Opener(store_path)
    deps = make_deps(opener, clock)
    opener.on_open = raise_when_called_from("_end_in_thread", [error])

    with caplog.at_level(logging.INFO):
        anyio.run(
            _run_until,
            deps,
            clock,
            "a row",
            _row_in(store_path),
        )

    assert f"session end failed: {type(error).__name__}: {error}" in [
        r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
    ]
    assert _exception_records(caplog) == []
    stale = FAST.session_stale_seconds
    assert len(sessions_in(store_path, clock(), stale)) == 1
    assert sessions_in(store_path, clock() + timedelta(seconds=stale), stale) == ()


def test_an_error_outside_the_set_at_exit_reaches_the_top_level_handler(
    store_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    clock = FakeClock()
    opener = Opener(store_path)
    deps = make_deps(opener, clock)
    opener.on_open = raise_when_called_from("_end_in_thread", [RuntimeError("a bug")])

    with caplog.at_level(logging.INFO):
        anyio.run(
            _run_until,
            deps,
            clock,
            "a row",
            _row_in(store_path),
        )

    (record,) = _exception_records(caplog)
    assert "presence stopped" in record.getMessage()
