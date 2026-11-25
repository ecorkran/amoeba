"""The session tick: what a failed tick does (slice 263, D4)."""

import logging
from pathlib import Path

import anyio
import pytest

from amoeba.client.errors import (
    ClientFileError,
    HubRefusedError,
    HubUnreachableError,
)
from amoeba.config.user_config import ConfigError
from amoeba.mcp import tick as tick_module
from amoeba.mcp.after_runner import AfterRunner
from amoeba.mcp.tick import run_ticks
from amoeba.store.errors import StoreBusyError, StoreCorruptError
from amoeba.store.vocabulary import DeliveryEvent
from amoeba.wire.protocol import RefusalCode
from mcp_server.presence_rig import (
    MEMBER_ID,
    RecordingOutbound,
    deliver,
    eventually,
    make_connection,
)
from mcp_server.tick_rig import (
    BEFORE_FIRST_REPLY,
    CLIENT,
    events_of,
    no_spawn,
    replied,
    run_tick,
    setup,
    warnings_of,
)

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
    state, deps, opener = setup(store_path, tmp_path, [error] * 3)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(replied(state), "a tick that succeeds")
        assert state.resolved.is_set()

    with caplog.at_level(logging.INFO):
        anyio.run(run_tick, deps, state, outbound, scenario)

    failures = [m for m in warnings_of(caplog) if m.startswith("tick failed:")]
    assert failures == [f"tick failed: {type(error).__name__}: {error}"]
    recovered = [r for r in caplog.records if r.getMessage() == "tick recovered"]
    assert [r.levelno for r in recovered] == [logging.INFO]
    assert opener.opens >= 4
    assert state.last_error is None
    assert state.member_id == MEMBER_ID


def test_busy_ticks_are_skipped_and_the_next_event_is_sent(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, opener = setup(store_path, tmp_path)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(replied(state), "the baseline")
        opener.errors.extend(StoreBusyError("locked") for _ in range(3))
        deliver(store_path, DeliveryEvent.SENT)
        await eventually(lambda: bool(events_of(outbound)), "the event after them")

    anyio.run(run_tick, deps, state, outbound, scenario)

    assert len(events_of(outbound)) == 1


def test_mail_waiting_before_the_first_successful_tick_is_not_pushed(
    store_path: Path, tmp_path: Path
) -> None:
    busy = [StoreBusyError("locked") for _ in range(4)]
    state, deps, opener = setup(store_path, tmp_path, busy)
    deliver(store_path, DeliveryEvent.SENT)
    outbound = RecordingOutbound()

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 7, "the baseline, then ticks")

    anyio.run(run_tick, deps, state, outbound, scenario)

    assert outbound.sent == []


def test_a_new_error_type_in_a_run_warns_again(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    errors = [
        StoreBusyError("locked"),
        StoreBusyError("locked"),
        HubUnreachableError("no reply"),
    ]
    state, deps, _ = setup(store_path, tmp_path, errors)

    async def scenario() -> None:
        await eventually(replied(state), "a tick that succeeds")

    with caplog.at_level(logging.INFO):
        anyio.run(run_tick, deps, state, RecordingOutbound(), scenario)

    assert len([m for m in warnings_of(caplog) if "tick failed" in m]) == 2


def test_a_failing_tick_resolves_presence_and_keeps_its_error(
    store_path: Path, tmp_path: Path
) -> None:
    blocked = [StoreBusyError("locked")] * 1000
    state, deps, opener = setup(store_path, tmp_path, blocked)

    async def scenario() -> None:
        await eventually(lambda: opener.opens >= 3, "ticks that fail")
        assert state.resolved.is_set()
        assert state.as_of_seq is None
        assert state.last_error == "StoreBusyError: locked"

    anyio.run(run_tick, deps, state, RecordingOutbound(), scenario)


def test_a_bug_in_a_tick_raises_out_of_the_loop(
    store_path: Path, tmp_path: Path
) -> None:
    state, deps, _ = setup(store_path, tmp_path, [RuntimeError("a bug")])

    async def run() -> None:
        runner = AfterRunner(deps, no_spawn)
        await run_ticks(
            make_connection(RecordingOutbound()), state, deps, CLIENT, runner
        )

    with pytest.raises(RuntimeError, match="a bug"):
        anyio.run(run)


def test_the_wait_is_five_seconds_before_a_reply_and_the_replys_after(
    store_path: Path, tmp_path: Path
) -> None:
    state, _, _ = setup(store_path, tmp_path)
    assert BEFORE_FIRST_REPLY == 5
    assert tick_module._interval(state) == 0.01  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001

    state.poll_seconds = 7.5

    assert tick_module._interval(state) == 7.5  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
