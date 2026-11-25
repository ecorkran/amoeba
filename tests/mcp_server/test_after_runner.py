"""The after-step runner (slice 263, D7): one at a time, in its own thread, and every
outcome logged by the run without ending presence or delaying a tick."""

from __future__ import annotations

import logging
import threading
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import anyio
import pytest

from amoeba.client.errors import HubRefusedError, HubUnreachableError
from amoeba.mcp import after_runner as after_runner_module
from amoeba.mcp import tick as tick_module
from amoeba.mcp.after_runner import AfterRunner
from amoeba.mcp.presence import PresenceDeps
from amoeba.mcp.tick import run_ticks
from amoeba.wire.protocol import RefusalCode
from amoeba.wiring_presence import LastReply, SessionIdentity, Steps
from mcp_server.presence_rig import (
    MEMBER_ID,
    FakeClock,
    Opener,
    RecordingOutbound,
    eventually,
    make_connection,
    make_deps,
    member_state,
)


@pytest.fixture(autouse=True)
def short_wait_before_the_first_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tick_module, "TICK_SECONDS_BEFORE_FIRST_REPLY", 0.01)


def _deps(store_path: Path) -> PresenceDeps:
    return make_deps(Opener(store_path), FakeClock())


def _fake_after_step(
    monkeypatch: pytest.MonkeyPatch, body: Callable[[], object]
) -> list[int]:
    """Replace the after-step's work with ``body``; the list counts its runs."""
    runs: list[int] = []

    def run_after_step(*args: Any, **kwargs: Any) -> None:
        runs.append(1)
        body()

    monkeypatch.setattr(after_runner_module, "run_after_step", run_after_step)
    return runs


async def _with_runner(
    deps: PresenceDeps, scenario: Callable[[AfterRunner], Awaitable[None]]
) -> None:
    async with anyio.create_task_group() as group:
        runner = AfterRunner(deps, lambda work: group.start_soon(work))
        await scenario(runner)


async def _finished(runner: AfterRunner) -> None:
    await eventually(lambda: not runner.running, "the after-step to end")


def test_a_slow_claim_starts_no_second_after_step_until_it_ends(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()
    runs = _fake_after_step(monkeypatch, lambda: release.wait(20))

    async def scenario(runner: AfterRunner) -> None:
        runner.start(LastReply(work=True))
        await eventually(lambda: bool(runs), "the first after-step")
        runner.start(LastReply(work=True))
        runner.start(LastReply(work=True))
        await anyio.sleep(0.05)
        assert len(runs) == 1
        release.set()
        await _finished(runner)
        runner.start(LastReply(work=True))
        await _finished(runner)

    anyio.run(_with_runner, _deps(store_path), scenario)

    assert len(runs) == 2


def test_a_slow_claim_delays_no_tick(
    store_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()
    runs = _fake_after_step(monkeypatch, lambda: release.wait(20))
    clock = FakeClock()
    opener = Opener(store_path)
    deps = make_deps(opener, clock)
    state = member_state(clock, tmp_path)

    async def run() -> None:
        async with anyio.create_task_group() as group:
            runner = AfterRunner(deps, lambda work: group.start_soon(work))
            group.start_soon(
                run_ticks,
                make_connection(RecordingOutbound()),
                state,
                deps,
                "claude-code",
                runner,
            )
            await eventually(lambda: bool(runs), "the after-step to start")
            seen = opener.opens
            await eventually(lambda: opener.opens >= seen + 4, "ticks while it runs")
            assert runner.running
            assert len(runs) == 1
            release.set()
            await _finished(runner)
            group.cancel_scope.cancel()

    anyio.run(run)

    assert state.member_id == MEMBER_ID


@pytest.mark.parametrize(
    "error",
    [
        HubUnreachableError("no reply"),
        HubRefusedError("refused", RefusalCode.HUB_ERROR),
    ],
    ids=["unknown", "refused"],
)
def test_an_unknown_or_refused_claim_starts_nothing_and_leaves_presence_alone(
    store_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    def fail() -> None:
        raise error

    runs = _fake_after_step(monkeypatch, fail)
    clock = FakeClock()
    state = member_state(clock, tmp_path)
    deps = make_deps(Opener(store_path), clock)

    async def run() -> None:
        async with anyio.create_task_group() as group:
            runner = AfterRunner(deps, lambda work: group.start_soon(work))
            group.start_soon(
                run_ticks,
                make_connection(RecordingOutbound()),
                state,
                deps,
                "claude-code",
                runner,
            )
            await eventually(lambda: len(runs) >= 3, "after-steps that fail")
            group.cancel_scope.cancel()

    with caplog.at_level(logging.INFO):
        anyio.run(run)

    assert state.member_id == MEMBER_ID
    assert state.last_error is None
    failed = [r for r in caplog.records if r.getMessage().startswith("after-step")]
    assert [r.levelno for r in failed] == [logging.WARNING]


def test_refused_on_ten_ticks_logs_one_warning_and_one_info_on_the_next_success(
    store_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    outcomes: list[Exception | None] = [
        *[HubRefusedError("refused", RefusalCode.HUB_ERROR) for _ in range(10)],
        None,
    ]

    def body() -> None:
        outcome = outcomes.pop(0)
        if outcome is not None:
            raise outcome

    _fake_after_step(monkeypatch, body)

    async def scenario(runner: AfterRunner) -> None:
        for _ in range(11):
            runner.start(LastReply(work=True))
            await _finished(runner)

    with caplog.at_level(logging.INFO):
        anyio.run(_with_runner, _deps(store_path), scenario)

    lines = [
        (r.levelno, r.getMessage())
        for r in caplog.records
        if r.getMessage().startswith("after-step")
    ]
    assert lines == [
        (logging.WARNING, "after-step failed: HubRefusedError: refused"),
        (logging.INFO, "after-step recovered"),
    ]


def test_a_flag_the_hub_could_not_work_out_is_logged_not_started(
    store_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    runs = _fake_after_step(monkeypatch, lambda: None)

    async def scenario(runner: AfterRunner) -> None:
        runner.start(LastReply(problem="the store is busy"))
        await _finished(runner)

    with caplog.at_level(logging.WARNING):
        anyio.run(_with_runner, _deps(store_path), scenario)

    assert runs == []
    assert any(
        "HubFlagProblem: the store is busy" in r.getMessage() for r in caplog.records
    )


def test_an_unexpected_raise_is_logged_and_the_next_tick_runs_the_after_step(
    store_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    outcomes: list[Exception | None] = [RuntimeError("a bug"), None]

    def body() -> None:
        outcome = outcomes.pop(0)
        if outcome is not None:
            raise outcome

    runs = _fake_after_step(monkeypatch, body)

    async def scenario(runner: AfterRunner) -> None:
        runner.start(LastReply(work=True))
        await _finished(runner)
        runner.start(LastReply(work=True))
        await _finished(runner)

    with caplog.at_level(logging.ERROR):
        anyio.run(_with_runner, _deps(store_path), scenario)

    assert len(runs) == 2
    (record,) = [r for r in caplog.records if r.exc_info is not None]
    assert "unexpectedly" in record.getMessage()


def test_the_tick_and_the_runner_each_open_their_own_store_in_their_own_thread(
    store_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    clock = FakeClock()
    opener = Opener(store_path)
    deps = make_deps(opener, clock)
    threads: list[int] = []

    @contextmanager
    def recording(
        last: LastReply, identity: SessionIdentity | None
    ) -> Generator[Steps]:
        threads.append(threading.get_ident())
        with opener(last, identity) as steps:
            yield steps

    recorded = PresenceDeps(recording, deps.cf_run, deps.clock, deps.after_deps)
    state = member_state(clock, tmp_path)

    async def run() -> None:
        async with anyio.create_task_group() as group:
            runner = AfterRunner(recorded, lambda work: group.start_soon(work))
            group.start_soon(
                run_ticks,
                make_connection(RecordingOutbound()),
                state,
                recorded,
                "claude-code",
                runner,
            )
            await eventually(lambda: len(threads) >= 6, "ticks and after-steps")
            group.cancel_scope.cancel()

    with caplog.at_level(logging.WARNING):
        anyio.run(run)

    assert state.member_id == MEMBER_ID
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
