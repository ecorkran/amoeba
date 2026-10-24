"""The resident process the Runner's crash proof runs (slice 122).

Run as ``python -m runner.crash_entry`` with ``PYTHONPATH`` at ``tests/``. It
composes the shipped tenants and a real :class:`RunnerTenant` whose only planner
is the proof planner, which launches the stub's no-op pipeline once for each node
id it was given. ``PROOF_KILL_AT`` names a point at which this process sends
itself ``SIGKILL``; the restarted process is started without it.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from functools import partial
from pathlib import Path

from contract.bootstrap import ReadyAnnouncer

from amoeba.process import (
    ProcessSettings,
    ResidentProcess,
    RunOutcome,
    RunOutcomeDocument,
    RunPoll,
    poll_run,
    standard_tenants,
)
from amoeba.runner.decide import Action, LaunchRun, ProjectView
from amoeba.runner.launch import LAUNCH_LOGS_DIRNAME
from amoeba.runner.probes import probe_sq
from amoeba.runner.tenant import RunnerTenant
from amoeba.store import Store
from runner.tick_support import runnable_unbusy

KILL_AT_ENV = "PROOF_KILL_AT"

#: The stub's no-op pipeline name; the stub ignores it.
PIPELINE = "noop"

IDLE_INTERVAL_SECONDS = 0.05
SHUTDOWN_GRACE_SECONDS = 5.0
CALL_TIMEOUT_SECONDS = 4.0
RUN_POLL_INTERVAL_SECONDS = 0.2
#: Short, so a restart that finds a stateless entry waits at most this long.
LAUNCH_GRACE_SECONDS = 2.0


class KillPoint(StrEnum):
    """Where the process sends itself ``SIGKILL``."""

    #: After the entry is journaled, before ``Popen``.
    BEFORE_LAUNCH = "before_launch"
    #: At the first poll that finds the run still running.
    WHILE_RUNNING = "while_running"
    #: At the first poll that finds the run finished, before it is recorded.
    AFTER_FINISH = "after_finish"
    #: After the node is blocked, as the entry is about to be resolved.
    BETWEEN_BLOCK_AND_RESOLVE = "between_block_and_resolve"


def die() -> None:
    """Die as a power cut would: nothing caught, flushed, or cleaned up."""
    os.kill(os.getpid(), signal.SIGKILL)


class ProofPlanner:
    """Launches once per given node id, ever (a marker file survives a crash)."""

    def __init__(self, node_ids: frozenset[str], checkout: Path, markers: Path) -> None:
        self._node_ids = node_ids
        self._checkout = checkout
        self._markers = markers

    def plan(self, view: ProjectView) -> Sequence[Action]:
        actions: list[Action] = []
        for node in runnable_unbusy(view):
            marker = self._markers / node.id
            if node.id in self._node_ids and not marker.exists():
                marker.touch()
                actions.append(LaunchRun(node.id, PIPELINE, {}, self._checkout))
        return actions


def _hooked(kill_at: KillPoint | None) -> tuple[object, object]:
    """The ``Popen`` and poll the Runner is given, armed for ``kill_at``."""

    def popen(argv: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
        if kill_at is KillPoint.BEFORE_LAUNCH:
            die()
        return subprocess.Popen(argv, **kwargs)  # type: ignore[call-overload]

    def poll(run_id: str) -> RunPoll:
        answer = poll_run(run_id, timeout_seconds=CALL_TIMEOUT_SECONDS)
        if isinstance(answer, RunOutcomeDocument):
            running = answer.outcome is RunOutcome.TIMED_OUT
            if kill_at is KillPoint.WHILE_RUNNING and running:
                die()
            if kill_at is KillPoint.AFTER_FINISH and answer.outcome in {
                RunOutcome.COMPLETED,
                RunOutcome.FAILED,
            }:
                die()
        return answer

    return popen, poll


def _arm_resolve_kill() -> None:
    """Make the next ``journal_resolve`` die: the node is already blocked."""
    original = Store.journal_resolve

    def resolve(self: Store, *args: object, **kwargs: object):  # noqa: ANN202
        die()
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    Store.journal_resolve = resolve  # type: ignore[method-assign]


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="runner.crash_entry")
    parser.add_argument("--supervisor-dir", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--markers-dir", type=Path, required=True)
    parser.add_argument("--node-id", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> None:
    arguments = parse_arguments(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    raw = os.environ.get(KILL_AT_ENV)
    kill_at = KillPoint(raw) if raw else None
    settings = ProcessSettings(
        idle_interval_seconds=IDLE_INTERVAL_SECONDS,
        shutdown_grace_seconds=SHUTDOWN_GRACE_SECONDS,
        launch_grace_seconds=LAUNCH_GRACE_SECONDS,
        tick_call_timeout_seconds=CALL_TIMEOUT_SECONDS,
        run_poll_interval_seconds=RUN_POLL_INTERVAL_SECONDS,
    )
    supervisor_dir: Path = arguments.supervisor_dir
    (supervisor_dir / LAUNCH_LOGS_DIRNAME).mkdir(parents=True, exist_ok=True)
    probe_sq(settings, datetime.now(UTC), poll_run)
    if kill_at is KillPoint.BETWEEN_BLOCK_AND_RESOLVE:
        _arm_resolve_kill()
    popen, poll = _hooked(kill_at)
    runner = RunnerTenant(
        settings=settings,
        supervisor_dir=supervisor_dir,
        planners=(
            ProofPlanner(
                frozenset(arguments.node_id), arguments.checkout, arguments.markers_dir
            ),
        ),
        popen=popen,  # type: ignore[arg-type]
        cf_run=subprocess.run,
        poll=poll,  # type: ignore[arg-type]
        now=partial(datetime.now, UTC),
        monotonic=time.monotonic,
    )
    process = ResidentProcess(
        settings,
        store_dir=supervisor_dir,
        version="runner-crash-proof",
        tenants=(
            *standard_tenants(settings, supervisor_dir),
            runner,
            ReadyAnnouncer(),
        ),
        exit_on_grace_expiry=True,
    )
    process.install_signal_handlers()
    process.run()


if __name__ == "__main__":
    main(sys.argv[1:])
