"""What the pause operations need from outside, bundled once (slice 223, task 5.3).

``Deps`` holds the ``cf`` runner, the one-shot run poll, the child spawner, the
clock, the sleep and the three directories. The CLI builds it with
:func:`production_deps`; a unit test builds it with fakes, so no test starts a real
process or waits in real time. It imports nothing from the operation modules that use
it, so there is no cycle.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Final

from amoeba.operations.processes import Spawner, start_child
from amoeba.upstream.context_forge.cli_call import CfRun
from amoeba.upstream.squadron.run_outcome import RunPoll, poll_run

#: One ``sq runs wait --timeout 0`` call reads a run file; a call this long is stuck.
RUN_POLL_TIMEOUT_SECONDS: Final = 30.0

#: Reads one run's outcome without waiting: ``poll_run`` with its timeout bound.
type PollRun = Callable[[str], RunPoll]


@dataclass(frozen=True)
class Deps:
    """The injectable edges of ``handle_pause`` and ``answer``."""

    cf_run: CfRun
    poll_run: PollRun
    spawn: Spawner
    clock: Callable[[], datetime]
    sleep: Callable[[float], None]
    #: Where each answering run's scratch directory goes (``answering_dir()``).
    answering_dir: Path
    #: Where answering and resume logs go (``logs_dir()``).
    logs_dir: Path
    #: Squadron's run files (``squadron_runs_dir()``).
    squadron_runs_dir: Path


def _utc_now() -> datetime:
    return datetime.now(UTC)


def production_deps(
    *, answering_dir: Path, logs_dir: Path, squadron_runs_dir: Path
) -> Deps:
    """The real edges: ``subprocess.run``, ``poll_run``, ``start_child``, the clock."""
    return Deps(
        cf_run=subprocess.run,
        poll_run=partial(poll_run, timeout_seconds=RUN_POLL_TIMEOUT_SECONDS),
        spawn=start_child,
        clock=_utc_now,
        sleep=time.sleep,
        answering_dir=answering_dir,
        logs_dir=logs_dir,
        squadron_runs_dir=squadron_runs_dir,
    )
