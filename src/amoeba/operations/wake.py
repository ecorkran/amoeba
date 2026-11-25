"""The hub part of ``send``'s wake step: claim a wake, or say who must (slice 244 D2,
D4; 262 D8).

After a request's transaction has committed, so the request is durable before any wake
work and nothing here can lose or change it, a read transaction checks whether a wake
is due (a recipient with no wake command on a checkout of this machine, or no mark,
fails with no write lock), then one write transaction claims it from this machine's
checkout. The claimed wake goes back in the result for the client part to start
(``wake_start``); a wake due only for other machines names them. A ``StoreError`` is
returned as one line, because the request is already written and a failed ``send``
would report a failure for work that happened; any other exception is a bug.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Final
from uuid import uuid4

from amoeba.config.user_config import UserConfig
from amoeba.operations.message_models import SendOutcome
from amoeba.operations.message_results import SendResult, WakeWaitingOn, WokenWake
from amoeba.operations.steps.limits import wake_limits
from amoeba.store.errors import StoreError
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store
from amoeba.store.vocabulary import RequestState
from amoeba.store.wakes import claim_wake, wake_due, wake_waiting_machines
from amoeba.wire.times import DOOR_VERSION

logger = logging.getLogger(__name__)

#: Under the logs directory: each wake's stdout and stderr logs. Old files here are
#: removed by ``prune`` like any other log (D10).
WAKE_LOG_DIRECTORY: Final = "wake"

#: The longest the wake step can take (D11): the store waits, each at most one busy
#: timeout: the legacy-move lock, the open, and up to three transactions (the read, the
#: claim and a failure write).
WAKE_BOUND_SECONDS: Final = 5 * BUSY_TIMEOUT_SECONDS


def claim_wake_for_send(  # noqa: PLR0913 - what the hub part of the step is given
    store: Store,
    config: UserConfig,
    now: datetime,
    member_id: str,
    result: SendResult,
    logs_dir: Path,
) -> SendResult:
    """``result`` with the wake the hub claimed for this machine, the machines a due
    wake waits for, or ``wake_problem``; unchanged when no wake applies.

    It applies while the stored request is ``open``: outcome ``sent``, or ``unchanged``
    with the request still ``open``. Never for ``accepted`` (an agent is on it), for a
    rejection, or for a note.
    """
    if not _request_is_open(result):
        return result
    try:
        return _claim(store, config, now, member_id, result, logs_dir)
    except StoreError as error:
        # The request is written; exit 3 would report a failure for work that
        # happened, so the failure is one line of the result instead.
        logger.exception("the wake step for %s failed", member_id)
        problem = f"waking {member_id} failed: {type(error).__name__}: {error}"
        return result.model_copy(update={"wake_problem": problem})


def _request_is_open(result: SendResult) -> bool:
    if result.outcome not in (SendOutcome.SENT, SendOutcome.UNCHANGED):
        return False
    return result.request is not None and result.request.state is RequestState.OPEN


def _claim(  # noqa: PLR0913 - what the hub part of the step is given
    store: Store,
    config: UserConfig,
    now: datetime,
    member_id: str,
    result: SendResult,
    logs_dir: Path,
) -> SendResult:
    limits = wake_limits(config, DOOR_VERSION)
    with store.read() as transaction:
        due_here = wake_due(transaction, member_id, now, limits)
        waiting = (
            ()
            if due_here
            else wake_waiting_machines(transaction, member_id, now, limits)
        )
    if not due_here:
        if not waiting:
            return result
        names = tuple(
            WakeWaitingOn(
                machine=name,
                last_called_at=None if called is None else encode_timestamp(called),
            )
            for name, called in waiting
        )
        return result.model_copy(update={"wake_waiting_on": names})
    wake_id = uuid4().hex
    log_stem = str(logs_dir / WAKE_LOG_DIRECTORY / wake_id)
    with store.write() as transaction:
        wake = claim_wake(transaction, member_id, now, limits, wake_id, log_stem)
    if wake is None:
        return result
    if wake.directory is None or wake.log_stem is None:
        raise AssertionError("a claimed wake has a directory and a log stem")
    woke = WokenWake(
        wake_id=wake.wake_id, directory=wake.directory, log_stem=wake.log_stem
    )
    return result.model_copy(update={"woke": woke})
