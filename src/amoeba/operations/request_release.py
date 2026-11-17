"""Start ``handle_pause`` for held questions whose request has ended (slice 242, D7).

``start_ended_held`` looks at every held row and its request's effective state
instead of being handed ids, so one function covers every way a request ends
(``reply``, ``cancel``, expiry, the ``rm`` cascade) and the retry of a start that was
lost or failed. Each start is the ordinary ``amoeba handle-pause``, detached in the
row's checkout; the caller never waits for it. A row is started at most once per
``answering_wait_seconds`` and at most ``MAX_STARTS_PER_CALL`` rows are started per
call; each child runs this function at its end too, so a larger batch drains on its
own. What this bounds is starts per call and per row, not live children: a burst of
ended requests can have every held question answering at once, one child per row.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

from amoeba.amoeba_script import AmoebaScriptMissing, handle_pause_argv
from amoeba.config.user_config import UserConfig
from amoeba.operations.answering_run import STDERR_LOG_SUFFIX, STDOUT_LOG_SUFFIX
from amoeba.operations.calls_log import append_call, error_entry, result_entry
from amoeba.operations.deps import Deps
from amoeba.operations.resume import LOG_STAMP_FORMAT
from amoeba.store.errors import StoreError, StoreRowError
from amoeba.store.held_questions import held_rows, mark_start_attempted
from amoeba.store.messages import effective_state, get_message
from amoeba.store.models import QuestionRecord
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store
from amoeba.store.vocabulary import RequestState
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs

logger = logging.getLogger(__name__)

#: Rows started per call; the rest wait for the next call or a child's own call.
MAX_STARTS_PER_CALL: Final = 5
#: The worst case of one call: the read, then one ``mark_start_attempted`` write per
#: start, each of which can wait the busy timeout. The spawn does not wait.
START_BOUND_SECONDS: Final = BUSY_TIMEOUT_SECONDS * (1 + MAX_STARTS_PER_CALL)
#: Under the state home's ``logs/``; pruned by age by the existing log walk.
REQUEST_RELEASE_LOG_DIRECTORY: Final = "request-release"
#: The calls-log outcome of a start that did not launch.
START_FAILED_OUTCOME: Final = "start_failed"


def start_ended_held(store: Store, config: UserConfig, deps: Deps) -> None:
    """Start ``handle_pause`` for each held row whose request has ended. Never
    raises: the caller's own work has committed, so a failure here is logged and
    written to the calls log, and the rows are found again by the next call."""
    try:
        due = _due_rows(store, config, deps.clock())
    except StoreError:
        # Not re-raised: the operation that called this has already committed, so
        # raising would report a failure for work that happened; the next call reads
        # the rows again. Every ``StoreError`` kind is safe here, not only a busy
        # store: this function writes nothing but ``start_attempted_at``, so a failed
        # read or write leaves each row as it was, and a store that is truly unusable
        # (corrupt, wrong schema, no permission) fails the next operation at its own
        # start, where it is reported. It is logged at ERROR, never silent.
        logger.exception("could not read the held questions to start")
        return
    if not due:
        return
    try:
        script = deps.amoeba_script()
    except AmoebaScriptMissing as error:
        # Not re-raised, for the reason above. Each row it would have started gets
        # an error line, so ``status`` shows why as the run's ``last_call``.
        logger.exception("the amoeba script is missing; held questions not started")
        now = deps.clock()
        for row in due:
            entry = error_entry(row.key.run_id, Path(row.checkout), error, now)
            append_call(deps.calls_log_dir, entry, now)
        return
    for row in due:
        try:
            with store.write() as transaction:
                marked = mark_start_attempted(
                    transaction, row.key, deps.clock(), row.start_attempted_at
                )
        except StoreError:
            # Not re-raised, for the reasons above (every store failure kind); the row
            # is retried next call.
            logger.exception("could not mark the start of %s", row.key)
            return
        # Another caller started it since this one read it, or it left the hold.
        if marked:
            _start(deps, script, row)


def _due_rows(store: Store, config: UserConfig, now: datetime) -> list[QuestionRecord]:
    """Held rows whose request is terminal or gone and whose last start is at least
    ``answering_wait_seconds`` old; never-attempted first, then oldest attempt."""
    wait = timedelta(seconds=config.answering_wait_seconds)
    due: list[QuestionRecord] = []
    with store.read() as transaction:
        for row in held_rows(transaction):
            if (
                row.start_attempted_at is not None
                and now - row.start_attempted_at < wait
            ):
                continue
            if row.request_id is None:
                raise StoreRowError(f"held question {row.key} has no request_id")
            message = get_message(transaction, row.request_id)
            if message is None:
                due.append(row)
                continue
            state = effective_state(message, now)
            if state in RequestState.terminal():
                due.append(row)
    due.sort(key=_start_order)
    return due[:MAX_STARTS_PER_CALL]


def _start_order(row: QuestionRecord) -> tuple[bool, datetime]:
    attempted = row.start_attempted_at
    return (attempted is not None, attempted or row.claimed_at)


def _start(deps: Deps, script: Path, row: QuestionRecord) -> None:
    run_id = row.key.run_id
    checkout = Path(row.checkout)
    started = deps.spawn(handle_pause_argv(script, run_id), checkout, _logs(deps, row))
    if isinstance(started, LaunchError):
        logger.error("could not start handle-pause for %s: %s", run_id, started.detail)
        now = deps.clock()
        entry = result_entry(
            run_id, checkout, START_FAILED_OUTCOME, None, started.detail, now
        )
        append_call(deps.calls_log_dir, entry, now)


def _logs(deps: Deps, row: QuestionRecord) -> LaunchLogs:
    directory = deps.logs_dir / REQUEST_RELEASE_LOG_DIRECTORY
    stem = f"{row.key.run_id}-{deps.clock().strftime(LOG_STAMP_FORMAT)}"
    return LaunchLogs(
        stdout=directory / f"{stem}{STDOUT_LOG_SUFFIX}",
        stderr=directory / f"{stem}{STDERR_LOG_SUFFIX}",
    )
