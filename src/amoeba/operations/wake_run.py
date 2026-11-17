"""``wake-run``: run a wake's command and record how it ended (slice 244, D6).

The wrapper is started by ``wake_after_send`` as ``amoeba wake-run <wake_id>``. It
reads its row, starts the row's command in a session of its own in the checkout, with
only the ``WAKE_ENV_NAMES`` variables, waits until the row's ``deadline_at``, stops the
command's process group, and records the outcome in one short write. It holds no store
lock while the command runs and loads no config: the deadline is in the row.

The command's stdout and stderr are the wrapper's own, which are the wake's logs. No
``detail`` and no log line holds argv text, because a command may have been written
with a secret in it; ``wake_detail`` is the one place the wrapper makes a detail text.
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from datetime import datetime
from typing import Final

from amoeba.operations.deps import Deps
from amoeba.operations.processes import (
    WaitableChild,
    WaitablePopen,
    terminate_group,
)
from amoeba.operations.wake_environment import build_wake_environment, wake_detail
from amoeba.store.errors import StoreBusyError, StoreError
from amoeba.store.models import Wake
from amoeba.store.store import Store
from amoeba.store.vocabulary import WakeOutcome
from amoeba.store.wakes import finish_wake, get_wake, set_command_pid

logger = logging.getLogger(__name__)

#: The ``amoeba`` subcommand that runs a wake: ``wake_after_send`` starts it, the CLI
#: registers it. Defined once, here, because the CLI imports from the operations.
WAKE_RUN_COMMAND: Final = "wake-run"


class WakeRunError(Exception):
    """Nothing can be recorded: the row is missing, already ended or unusable. The
    wrapper runs no command and exits 3; a row that exists stays unended and leaves by
    its deadline and the retention."""


class _StartFailure(Exception):  # noqa: N818 - an internal signal, not a public error
    """The command could not be started; ``detail`` is safe to record."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def run_wake(
    store: Store,
    deps: Deps,
    wake_id: str,
    popen: WaitablePopen = subprocess.Popen,
) -> WakeOutcome:
    """Run the wake ``wake_id`` to its end and return how it was recorded.

    Raises:
        WakeRunError: The row is missing or already ended; no command ran.
        StoreError: The store cannot be read, or the end cannot be written; the row
            is left as it was.
    """
    wake = _unended_row(store, wake_id)
    child: WaitableChild | None = None
    try:
        child = _start(wake, popen)
        if not _record_pid(store, wake_id, child.pid):
            # A second run of the same wake got there first: its command stands, and
            # this one is stopped by the handler below.
            raise WakeRunError(f"wake {wake_id!r} was started by another run")
        outcome, exit_code = _wait(child, wake.deadline_at, deps.clock())
        terminate_group(child)
        _finish(store, deps, wake_id, outcome, exit_code, None)
        return outcome
    except _StartFailure as failure:
        logger.error("wake %s: the command did not start: %s", wake_id, failure.detail)
        _finish(store, deps, wake_id, WakeOutcome.START_FAILED, None, failure.detail)
        return WakeOutcome.START_FAILED
    except (WakeRunError, StoreError):
        # Nothing more can be recorded, but a command already started must not run on
        # past its deadline with no wrapper: stop its group, then report (exit 3).
        if child is not None:
            terminate_group(child)
        raise
    except Exception as error:  # process boundary: the wrapper's own unexpected error
        logger.exception("wake %s: the wrapper failed", wake_id)
        if child is not None:
            terminate_group(child)
        outcome = (
            WakeOutcome.START_FAILED if child is None else WakeOutcome.WRAPPER_FAILED
        )
        _finish(store, deps, wake_id, outcome, None, wake_detail(error))
        return outcome


def _unended_row(store: Store, wake_id: str) -> Wake:
    with store.read() as transaction:
        wake = get_wake(transaction, wake_id)
    if wake is None:
        raise WakeRunError(f"there is no wake {wake_id!r}")
    if wake.ended_at is not None:
        raise WakeRunError(f"wake {wake_id!r} has already ended")
    if wake.directory is None:
        raise WakeRunError(f"wake {wake_id!r} has no checkout to run in")
    if wake.command_pid is not None:
        raise WakeRunError(f"wake {wake_id!r} already has a command running")
    return wake


def _start(wake: Wake, popen: WaitablePopen) -> WaitableChild:
    """Start the row's command; a failure the world causes is a ``_StartFailure``."""
    try:
        argv = shlex.split(wake.command)
    except ValueError as error:
        raise _StartFailure(wake_detail(error)) from error
    try:
        return popen(
            argv,
            cwd=wake.directory,
            env=build_wake_environment(os.environ),
            start_new_session=True,
            stdin=subprocess.DEVNULL,
        )
    except OSError as error:
        # Not found, not executable, no such directory: recorded as a start failure,
        # without the file name (it may carry a secret).
        raise _StartFailure(wake_detail(error)) from error


def _record_pid(store: Store, wake_id: str, pid: int) -> bool:
    """Whether this run is the one whose command the row names; a held store is a
    warning and counts as yes, since the wake goes on and its row shows no pid."""
    try:
        with store.write() as transaction:
            return set_command_pid(transaction, wake_id, pid)
    except StoreBusyError:
        # Expected when the store is held: the wake goes on, and its row shows no pid.
        logger.warning("wake %s: could not record the command pid", wake_id)
        return True


def _wait(
    child: WaitableChild, deadline: datetime, now: datetime
) -> tuple[WakeOutcome, int | None]:
    """How the command ended: its exit code, or a timeout at ``deadline``."""
    try:
        code = child.wait(timeout=max(0.0, (deadline - now).total_seconds()))
    except subprocess.TimeoutExpired:
        # Expected: the command outlived the wake; the caller stops its group.
        return WakeOutcome.TIMED_OUT, None
    return WakeOutcome.EXITED, code


def _finish(
    store: Store,
    deps: Deps,
    wake_id: str,
    outcome: WakeOutcome,
    exit_code: int | None,
    detail: str | None,
) -> None:
    """One short write that ends the row; a failure is logged once and raised."""
    try:
        with store.write() as transaction:
            ended = finish_wake(
                transaction, wake_id, outcome, exit_code, detail, deps.clock()
            )
    except StoreError:
        logger.exception("wake %s: could not record how it ended", wake_id)
        raise
    if not ended:
        # Something else ended the row first; its record stands (a compare-and-set).
        logger.warning(
            "wake %s: was already recorded as ended; kept as it was", wake_id
        )
