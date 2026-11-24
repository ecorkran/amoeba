"""``wake-run``: run a wake's command and record how it ended (slice 244, D6).

The wrapper is started by ``wake_after_send`` as ``amoeba wake-run <wake_id>``. It
reads its row (``wake_read``), starts the row's command in a session of its own in
the checkout, with only the ``WAKE_ENV_NAMES`` variables, records its pid
(``wake_set_pid``), waits the time the hub said the wake has left, stops the command's
process group, and records the outcome (``wake_finish``). It holds no store lock while
the command runs and loads no config: the deadline is in the row.

A step that gets no reply or is refused stops the wrapper (262 D11): at ``wake_read``
and ``wake_finish`` exit 3; at ``wake_set_pid`` with no reply it goes on, with a
warning, because the command is already running; refused, its process group is stopped.

The command's stdout and stderr are the wrapper's own, which are the wake's logs. No
``detail`` and no log line holds argv text, because a command may have been written
with a secret in it; ``wake_detail`` is the one place the wrapper makes a detail text.
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from typing import Final

from amoeba.client.errors import HubRefusedError, HubUnreachableError
from amoeba.operations.processes import (
    WaitableChild,
    WaitablePopen,
    terminate_group,
)
from amoeba.operations.steps.models import (
    WAKE_FINISH,
    WAKE_READ,
    WAKE_SET_PID,
)
from amoeba.operations.steps.models_wake import (
    WakeFinishRequest,
    WakeReadRequest,
    WakeSetPidRequest,
    WakeToRun,
)
from amoeba.operations.store_steps import Steps
from amoeba.operations.wake_environment import build_wake_environment, wake_detail
from amoeba.store.errors import StoreBusyError, StoreError
from amoeba.store.vocabulary import WakeOutcome

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
    steps: Steps,
    wake_id: str,
    popen: WaitablePopen = subprocess.Popen,
) -> WakeOutcome:
    """Run the wake ``wake_id`` to its end and return how it was recorded.

    Raises:
        WakeRunError: The row is missing, not this machine's or already ended; no
            command ran.
        StoreError, HubUnreachableError, HubRefusedError: A step failed; a command
            already started is stopped first, and the row is left as it was.
    """
    wake = _read(steps, wake_id)
    child: WaitableChild | None = None
    try:
        child = _start(wake, popen)
        if not _record_pid(steps, wake_id, child.pid):
            # A second run of the same wake got there first: its command stands, and
            # this one is stopped by the handler below.
            raise WakeRunError(f"wake {wake_id!r} was started by another run")
        outcome, exit_code = _wait(child, wake.seconds_left)
        terminate_group(child)
        _finish(steps, wake_id, outcome, exit_code, None)
        return outcome
    except _StartFailure as failure:
        logger.error("wake %s: the command did not start: %s", wake_id, failure.detail)
        _finish(steps, wake_id, WakeOutcome.START_FAILED, None, failure.detail)
        return WakeOutcome.START_FAILED
    except (WakeRunError, StoreError, HubUnreachableError, HubRefusedError):
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
        _finish(steps, wake_id, outcome, None, wake_detail(error))
        return outcome


def _read(steps: Steps, wake_id: str) -> WakeToRun:
    reply = steps.run(WAKE_READ, WakeReadRequest(wake_id=wake_id))
    if reply.wake is None:
        raise WakeRunError(reply.problem or f"wake {wake_id!r} cannot be run")
    return reply.wake


def _start(wake: WakeToRun, popen: WaitablePopen) -> WaitableChild:
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


def _record_pid(steps: Steps, wake_id: str, pid: int) -> bool:
    """Whether this run is the one whose command the row names. A step with no reply
    (a held store, or a hub that does not answer) is a warning and counts as yes: the
    command is already running, the wake goes on and its row shows no pid."""
    try:
        return steps.run(
            WAKE_SET_PID, WakeSetPidRequest(wake_id=wake_id, pid=pid)
        ).recorded
    except (StoreBusyError, HubUnreachableError):
        # Expected when the store is held or the hub is away: the wake goes on.
        logger.warning("wake %s: could not record the command pid", wake_id)
        return True


def _wait(child: WaitableChild, seconds_left: float) -> tuple[WakeOutcome, int | None]:
    """How the command ended: its exit code, or a timeout once the wake's time is up."""
    try:
        code = child.wait(timeout=seconds_left)
    except subprocess.TimeoutExpired:
        # Expected: the command outlived the wake; the caller stops its group.
        return WakeOutcome.TIMED_OUT, None
    return WakeOutcome.EXITED, code


def _finish(
    steps: Steps,
    wake_id: str,
    outcome: WakeOutcome,
    exit_code: int | None,
    detail: str | None,
) -> None:
    """One step that ends the row; a failure is logged once and raised."""
    try:
        ended = steps.run(
            WAKE_FINISH,
            WakeFinishRequest(
                wake_id=wake_id, outcome=outcome, exit_code=exit_code, detail=detail
            ),
        ).ended
    except (StoreError, HubUnreachableError, HubRefusedError):
        logger.exception("wake %s: could not record how it ended", wake_id)
        raise
    if not ended:
        # Something else ended the row first; its record stands (a compare-and-set).
        logger.warning(
            "wake %s: was already recorded as ended; kept as it was", wake_id
        )
