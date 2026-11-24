"""The client part of ``send``'s wake step: start the wrapper for a claimed wake
(slice 244 D5; 262 D8).

The hub part claimed the wake and returned it in the result. This starts
``amoeba wake-run <wake id>`` detached in the wake's checkout, returns without waiting,
and records a start that fails as ``start_failed`` (``wake_finish``): the request stays
``open`` and a wake that failed to start is not tried again (D8). A failure to record
that is one line of the result, never a failed ``send``.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from amoeba.amoeba_script import AmoebaScriptMissing
from amoeba.client.errors import HubRefusedError, HubUnreachableError
from amoeba.operations.deps import Deps
from amoeba.operations.message_results import SendResult, WokenWake
from amoeba.operations.processes import WaitableChild
from amoeba.operations.steps.models import WAKE_FINISH
from amoeba.operations.steps.models_wake import WakeFinishRequest
from amoeba.operations.store_steps import Steps
from amoeba.operations.wake_run import WAKE_RUN_COMMAND
from amoeba.store.errors import StoreError
from amoeba.store.vocabulary import WakeOutcome
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs

logger = logging.getLogger(__name__)

STDOUT_LOG_SUFFIX = ".stdout.log"
STDERR_LOG_SUFFIX = ".stderr.log"


def start_woken_wake(steps: Steps, deps: Deps, result: SendResult) -> SendResult:
    """``result`` with ``wake_problem`` set when recording a failed start failed; the
    wrapper is started when the result carries a claimed wake."""
    if result.woke is None:
        return result
    try:
        _start_wrapper(steps, deps, result.woke)
    except (StoreError, HubUnreachableError, HubRefusedError) as error:
        logger.exception("could not record a failed wake start")
        problem = f"waking failed: {type(error).__name__}: {error}"
        return result.model_copy(update={"wake_problem": problem})
    return result


def start_woken_wake_item(
    steps: Steps, deps: Deps, wake: WokenWake, *, failed_with: str | None = None
) -> None:
    """Start the wrapper for a wake ``claim_work`` handed out, or, with
    ``failed_with``, end it as ``start_failed`` because the start could not be made.
    Never raises: a failure to record is logged, and the wake's claim runs out."""
    try:
        if failed_with is None:
            _start_wrapper(steps, deps, wake)
        else:
            _record_start_failure(steps, wake, failed_with)
    except (StoreError, HubUnreachableError, HubRefusedError):
        logger.exception("could not record a failed wake start")


def _start_wrapper(steps: Steps, deps: Deps, wake: WokenWake) -> None:
    """Start ``amoeba wake-run`` for the claimed wake, detached. A start that fails is
    recorded on the row and logged, and the request stays ``open`` (D5)."""
    try:
        script = deps.amoeba_script()
    except AmoebaScriptMissing as error:
        # Raising would report a failure for a request that is already written.
        _record_start_failure(steps, wake, str(error))
        return
    started = deps.spawn(
        [str(script), WAKE_RUN_COMMAND, wake.wake_id],
        Path(wake.directory),
        LaunchLogs(
            stdout=Path(f"{wake.log_stem}{STDOUT_LOG_SUFFIX}"),
            stderr=Path(f"{wake.log_stem}{STDERR_LOG_SUFFIX}"),
        ),
    )
    if isinstance(started, LaunchError):
        _record_start_failure(steps, wake, started.detail)
        return
    _reap_when_done(started)


def _reap_when_done(child: WaitableChild) -> None:
    """Wait for the wrapper on a daemon thread, so it never lingers as a zombie in a
    long-lived process (``amoeba-mcp``) that does not start another child soon. The
    thread ends when the wrapper does, and never outlives the process."""
    threading.Thread(target=child.wait, daemon=True, name="wake-reaper").start()


def _record_start_failure(steps: Steps, wake: WokenWake, detail: str) -> None:
    """End the claimed row as ``start_failed``. If the step fails, the row stays
    unended and reads as running until its deadline, then overdue: that is D5's stated
    exit, and ``wake_problem`` reports it."""
    logger.error("wake %s could not start its wrapper: %s", wake.wake_id, detail)
    steps.run(
        WAKE_FINISH,
        WakeFinishRequest(
            wake_id=wake.wake_id,
            outcome=WakeOutcome.START_FAILED,
            exit_code=None,
            detail=detail,
        ),
    )
