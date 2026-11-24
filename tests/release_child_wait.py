"""Waiting for a detached ``handle-pause`` child started by the after-step
(slice 242). One helper and one set of bounds for every test that waits on one."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Final

from amoeba.config.home import logs_dir
from amoeba.operations.work_start import HANDLE_PAUSE_LOG_DIRECTORY

#: How long a test waits for a real child to start, run and exit.
CHILD_WAIT_SECONDS: Final = 60.0
CHILD_POLL_INTERVAL_SECONDS: Final = 0.2


def child_finished(run_id: str) -> bool:
    """The child's stdout log exists, and its calls-log line (written as it exits)
    is in."""
    release_logs = logs_dir() / HANDLE_PAUSE_LOG_DIRECTORY
    logged = list(release_logs.glob(f"{run_id}-*.stdout.log"))
    days = list((logs_dir() / "calls").glob("*.jsonl"))
    return bool(logged) and any(run_id in day.read_text() for day in days)


def wait_until(done: Callable[[], bool], failure: Callable[[], str]) -> None:
    """Poll ``done`` every ``CHILD_POLL_INTERVAL_SECONDS``; at
    ``CHILD_WAIT_SECONDS`` fail with ``failure()``."""
    deadline = time.monotonic() + CHILD_WAIT_SECONDS
    while not done():
        if time.monotonic() >= deadline:
            raise AssertionError(failure())
        time.sleep(CHILD_POLL_INTERVAL_SECONDS)
