"""The wake step of ``send``: claim a wake, start its wrapper (slice 244, D2, D4, D5).

``send`` calls ``wake_for_sent_request`` after a request's transaction has committed,
so the request is durable before any wake work and nothing here can lose or change it.
Most sends do no wake work: a read transaction checks the conditions first (a recipient
with no wake command on a checkout here fails them, with no write lock), then one write
transaction claims the wake from that checkout, then the wrapper is started detached and
the step returns without waiting (261 D9).

The step makes no ``cf`` call and no ``ps`` call. A ``StoreError`` is returned as one
line, because the request is already written and a failed ``send`` would report a
failure for work that happened; any other exception is a bug and propagates.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Final
from uuid import uuid4

from amoeba.amoeba_script import AmoebaScriptMissing
from amoeba.config.user_config import UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.message_member import Recipient
from amoeba.operations.message_models import SendOutcome
from amoeba.operations.message_results import SendResult
from amoeba.operations.processes import WaitableChild
from amoeba.operations.wake_run import WAKE_RUN_COMMAND
from amoeba.store.errors import StoreError
from amoeba.store.models import Wake
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store
from amoeba.store.vocabulary import RequestState, WakeOutcome
from amoeba.store.wakes import WakeLimits, can_wake, claim_wake, finish_wake
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs

logger = logging.getLogger(__name__)

#: Under the logs directory: each wake's stdout and stderr logs. Old files here are
#: removed by ``prune`` like any other log (D10).
WAKE_LOG_DIRECTORY: Final = "wake"
STDOUT_LOG_SUFFIX: Final = ".stdout.log"
STDERR_LOG_SUFFIX: Final = ".stderr.log"

#: The longest the wake step can take (D11): the store waits, each at most one busy
#: timeout: the legacy-move lock, the open, and up to three transactions (the read, the
#: claim and a failure write).
WAKE_BOUND_SECONDS: Final = 5 * BUSY_TIMEOUT_SECONDS


def wake_limits(config: UserConfig) -> WakeLimits:
    """The limits a claim and a due-check apply, from the config."""
    return WakeLimits(
        timeout_seconds=config.wake_timeout_seconds,
        max_per_day=config.max_wakes_per_day,
        session_stale_seconds=config.session_stale_seconds,
    )


def wake_for_sent_request(
    store: Store,
    config: UserConfig,
    deps: Deps,
    recipient: Recipient,
    result: SendResult,
) -> SendResult:
    """``result`` with ``wake_problem`` set, after the wake step when it applies.

    It applies while the stored request is ``open``: outcome ``sent``, or ``unchanged``
    with the request still ``open``. Never for ``accepted`` (an agent is on it), for a
    rejection, or for a note.
    """
    if not _request_is_open(result):
        return result
    problem = wake_after_send(store, config, deps, recipient)
    if problem is None:
        return result
    return result.model_copy(update={"wake_problem": problem})


def _request_is_open(result: SendResult) -> bool:
    if result.outcome not in (SendOutcome.SENT, SendOutcome.UNCHANGED):
        return False
    return result.request is not None and result.request.state is RequestState.OPEN


def wake_after_send(
    store: Store, config: UserConfig, deps: Deps, recipient: Recipient
) -> str | None:
    """Claim a wake for ``recipient`` and start its wrapper; a problem line or ``None``.

    Returns without waiting for the wrapper.
    """
    try:
        return _claim_and_start(store, config, deps, recipient)
    except StoreError as error:
        # The request is written; exit 3 would report a failure for work that
        # happened, so the failure is one line of the result instead.
        logger.exception("the wake step for %s failed", recipient.member_id)
        return f"waking {recipient.member_id} failed: {type(error).__name__}: {error}"


def _claim_and_start(
    store: Store, config: UserConfig, deps: Deps, recipient: Recipient
) -> str | None:
    now = deps.clock()
    limits = wake_limits(config)
    with store.read() as transaction:
        wakeable = can_wake(transaction, recipient.member_id, now, limits)
    if not wakeable:
        return None
    wake_id = uuid4().hex
    log_stem = str(deps.logs_dir / WAKE_LOG_DIRECTORY / wake_id)
    with store.write() as transaction:
        wake = claim_wake(
            transaction, recipient.member_id, now, limits, wake_id, log_stem
        )
    if wake is None:
        return None
    return _start_wrapper(store, deps, wake)


def _start_wrapper(store: Store, deps: Deps, wake: Wake) -> str | None:
    """Start ``amoeba wake-run`` for the claimed row, detached. A start that fails is
    recorded on the row and logged, and the request stays ``open`` (D5)."""
    if wake.directory is None or wake.log_stem is None:
        raise AssertionError("a claimed wake has a directory and a log stem")
    try:
        script = deps.amoeba_script()
    except AmoebaScriptMissing as error:
        # Raising would report a failure for a request that is already written.
        _record_start_failure(store, deps, wake, str(error))
        return None
    started = deps.spawn(
        [str(script), WAKE_RUN_COMMAND, wake.wake_id],
        Path(wake.directory),
        LaunchLogs(
            stdout=Path(f"{wake.log_stem}{STDOUT_LOG_SUFFIX}"),
            stderr=Path(f"{wake.log_stem}{STDERR_LOG_SUFFIX}"),
        ),
    )
    if isinstance(started, LaunchError):
        _record_start_failure(store, deps, wake, started.detail)
        return None
    _reap_when_done(started)
    return None


def _reap_when_done(child: WaitableChild) -> None:
    """Wait for the wrapper on a daemon thread, so it never lingers as a zombie in a
    long-lived process (``amoeba-mcp``) that does not start another child soon. The
    thread ends when the wrapper does, and never outlives the process."""
    threading.Thread(target=child.wait, daemon=True, name="wake-reaper").start()


def _record_start_failure(store: Store, deps: Deps, wake: Wake, detail: str) -> None:
    """End the claimed row as ``start_failed``. If the write fails (a ``StoreError``,
    caught by the wake step), the row stays unended and reads as running until its
    deadline, then overdue: that is D5's stated exit, and ``wake_problem`` reports it.
    """
    logger.error("wake %s could not start its wrapper: %s", wake.wake_id, detail)
    now: datetime = deps.clock()
    with store.write() as transaction:
        finish_wake(
            transaction, wake.wake_id, WakeOutcome.START_FAILED, None, detail, now
        )
