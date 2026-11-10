"""Fakes for the pause operations' injected edges (slice 223): a clock, a sleep, a
child and a spawner that records what it was asked to start."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cf_plan_run import plan_cf_run
from fake_sq import FakePoller, fake_poller

from amoeba.operations.deps import Deps
from amoeba.operations.processes import Spawner, WaitableChild
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs
from amoeba.upstream.squadron.run_outcome import RunPoll

START = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
#: A pid no process holds, so a stray group stop reaches nothing.
UNUSED_PID = 2_000_000_000


@dataclass
class FakeClock:
    """A clock that moves only when a test says so."""

    now: datetime = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@dataclass
class FakeSleep:
    """Records each sleep and advances the clock by it."""

    clock: FakeClock
    calls: list[float] = field(default_factory=lambda: [])

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        self.clock.advance(seconds)


@dataclass
class FakeChild:
    """A child that has exited with ``exit_code``, or never does (``exit_code`` None
    raises ``TimeoutExpired`` from ``wait``)."""

    exit_code: int | None
    pid: int = UNUSED_PID

    def poll(self) -> int | None:
        return self.exit_code

    def wait(self, timeout: float | None = None) -> int:
        if self.exit_code is None:
            raise subprocess.TimeoutExpired("fake", timeout or 0)
        return self.exit_code


@dataclass(frozen=True)
class SpawnCall:
    argv: tuple[str, ...]
    cwd: Path
    logs: LaunchLogs


@dataclass
class SpawnRecorder:
    """A spawner that records calls and returns the next scripted child or error.

    ``on_spawn`` runs inside each call, before it returns, so a test can look at the
    world while a spawn is in flight (for example, that no transaction is open).
    """

    results: list[WaitableChild | LaunchError]
    on_spawn: Callable[[], None] | None = None
    calls: list[SpawnCall] = field(default_factory=lambda: [])

    def __call__(
        self, argv: Sequence[str], cwd: Path, logs: LaunchLogs
    ) -> WaitableChild | LaunchError:
        if self.on_spawn is not None:
            self.on_spawn()
        self.calls.append(SpawnCall(tuple(argv), cwd, logs))
        position = min(len(self.calls) - 1, len(self.results) - 1)
        return self.results[position]


@dataclass
class DepsRig:
    """The injected edges of one test, with the fakes kept for assertions."""

    deps: Deps
    clock: FakeClock
    sleep: FakeSleep
    spawner: SpawnRecorder
    poller: FakePoller


def build_deps(
    tmp_path: Path,
    *,
    polls: Mapping[str, Sequence[RunPoll]],
    spawns: list[WaitableChild | LaunchError],
    spawner: Spawner | None = None,
    on_spawn: Callable[[], None] | None = None,
    on_poll: Callable[[], None] | None = None,
) -> DepsRig:
    """Deps over fakes. ``spawner`` replaces the recorder (for a real child)."""
    clock = FakeClock()
    sleep = FakeSleep(clock)
    recorder = SpawnRecorder(spawns, on_spawn)
    poller = fake_poller(polls)

    def poll(run_id: str) -> RunPoll:
        if on_poll is not None:
            on_poll()
        return poller(run_id, timeout_seconds=0)

    deps = Deps(
        cf_run=plan_cf_run(integration_branch="", broken=False),
        poll_run=poll,
        spawn=spawner or recorder,
        clock=clock,
        sleep=sleep,
        answering_dir=tmp_path / "answering",
        logs_dir=tmp_path / "logs",
        squadron_runs_dir=tmp_path / "runs",
    )
    return DepsRig(deps, clock, sleep, recorder, poller)
