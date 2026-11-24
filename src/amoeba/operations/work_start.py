"""Start the work ``claim_work`` handed out, detached (slice 262, D10).

Each item is started in a session of its own with its own logs and never waited on: a
resume as ``amoeba resume-run <answer seq> <claim id>``, a held question or a dead
claim as ``amoeba handle-pause <run id>`` in its checkout, a wake as
``amoeba wake-run <wake id>``. ``start_claimed`` never raises and never changes the
result of the call it follows: a start that fails is logged and recorded where its kind
records one (a refused resume, a ``start_failed`` wake, a calls-log line for a
``handle-pause``), and the claim runs out and is handed out again.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from amoeba.amoeba_script import AmoebaScriptMissing, handle_pause_argv
from amoeba.client.errors import HubRefusedError, HubUnreachableError
from amoeba.operations.answering_run import STDERR_LOG_SUFFIX, STDOUT_LOG_SUFFIX
from amoeba.operations.calls_log import append_call, result_entry
from amoeba.operations.deps import Deps
from amoeba.operations.message_results import WokenWake
from amoeba.operations.resume import LOG_STAMP_FORMAT
from amoeba.operations.resume_run import RESUME_RUN_COMMAND
from amoeba.operations.steps.models import RESUME_RECORD
from amoeba.operations.steps.models_resume import ResumeRecordRequest
from amoeba.operations.steps.models_work import (
    HandlePauseItem,
    ResumeItem,
    WakeItem,
    WorkItem,
)
from amoeba.operations.store_steps import Steps
from amoeba.operations.wake_start import start_woken_wake_item
from amoeba.store.errors import StoreError
from amoeba.store.vocabulary import ResumeOutcome
from amoeba.upstream.squadron.launch import LaunchError, LaunchLogs

logger = logging.getLogger(__name__)

#: Under ``logs/``: the output of each detached ``resume-run`` and ``handle-pause``.
RESUME_RUN_LOG_DIRECTORY: Final = "resume-run"
HANDLE_PAUSE_LOG_DIRECTORY: Final = "handle-pause"
#: The calls-log outcome of a ``handle-pause`` that did not launch.
START_FAILED_OUTCOME: Final = "start_failed"


def start_claimed(steps: Steps, deps: Deps, items: Sequence[WorkItem]) -> None:
    """Start each item detached; never waits and never raises."""
    if not items:
        return
    try:
        script = deps.amoeba_script()
    except AmoebaScriptMissing as error:
        # Not re-raised: the call this follows has committed. Each item is recorded as
        # a failed start where its kind records one, so ``list`` shows why.
        logger.exception("the amoeba script is missing; claimed work not started")
        for item in items:
            _record_failed_start(steps, deps, item, str(error))
        return
    for item in items:
        _start_one(steps, deps, script, item)


def _start_one(steps: Steps, deps: Deps, script: Path, item: WorkItem) -> None:
    match item:
        case ResumeItem():
            _spawn_resume(steps, deps, script, item)
        case HandlePauseItem():
            _spawn_handle_pause(deps, script, item)
        case WakeItem():
            start_woken_wake_item(
                steps,
                deps,
                WokenWake(
                    wake_id=item.wake_id,
                    directory=item.directory,
                    log_stem=item.log_stem,
                ),
            )


def _spawn_resume(steps: Steps, deps: Deps, script: Path, item: ResumeItem) -> None:
    stem = f"{item.answer_seq}-{deps.clock().strftime(LOG_STAMP_FORMAT)}"
    started = deps.spawn(
        [str(script), RESUME_RUN_COMMAND, str(item.answer_seq), item.claim_id],
        deps.logs_dir.parent,
        _logs(deps, RESUME_RUN_LOG_DIRECTORY, stem),
    )
    if isinstance(started, LaunchError):
        _record_failed_start(steps, deps, item, started.detail)


def _spawn_handle_pause(deps: Deps, script: Path, item: HandlePauseItem) -> None:
    checkout = Path(item.checkout)
    stem = f"{item.run_id}-{deps.clock().strftime(LOG_STAMP_FORMAT)}"
    started = deps.spawn(
        handle_pause_argv(script, item.run_id),
        checkout,
        _logs(deps, HANDLE_PAUSE_LOG_DIRECTORY, stem),
    )
    if isinstance(started, LaunchError):
        _log_failed_handle_pause(deps, item, started.detail)


def _logs(deps: Deps, directory: str, stem: str) -> LaunchLogs:
    root = deps.logs_dir / directory
    return LaunchLogs(
        stdout=root / f"{stem}{STDOUT_LOG_SUFFIX}",
        stderr=root / f"{stem}{STDERR_LOG_SUFFIX}",
    )


def _record_failed_start(steps: Steps, deps: Deps, item: WorkItem, detail: str) -> None:
    """A start that did not launch, recorded where its kind records one."""
    logger.error("could not start %s work: %s", item.kind, detail)
    match item:
        case ResumeItem():
            _record_refused_resume(steps, item, detail)
        case HandlePauseItem():
            _log_failed_handle_pause(deps, item, detail)
        case WakeItem():
            start_woken_wake_item(
                steps,
                deps,
                WokenWake(
                    wake_id=item.wake_id,
                    directory=item.directory,
                    log_stem=item.log_stem,
                ),
                failed_with=detail,
            )


def _record_refused_resume(steps: Steps, item: ResumeItem, detail: str) -> None:
    try:
        steps.run(
            RESUME_RECORD,
            ResumeRecordRequest(
                answer_seq=item.answer_seq,
                claim_id=item.claim_id,
                outcome=ResumeOutcome.REFUSED,
                detail=detail,
                log=None,
            ),
        )
    except (StoreError, HubUnreachableError, HubRefusedError):
        # Not re-raised: the claim runs out and the resume is handed out again.
        logger.exception("could not record a failed resume start")


def _log_failed_handle_pause(deps: Deps, item: HandlePauseItem, detail: str) -> None:
    logger.error("could not start handle-pause for %s: %s", item.run_id, detail)
    now = deps.clock()
    entry = result_entry(
        item.run_id, Path(item.checkout), START_FAILED_OUTCOME, None, detail, now
    )
    append_call(deps.calls_log_dir, entry, now)
