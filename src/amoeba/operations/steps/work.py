"""``work_waiting`` and ``claim_work``: work that belongs to a machine (262 D10).

``work_waiting`` is the flag every done reply carries: four existence checks on records
that already exist, stopping at the first hit. ``claim_work`` claims up to
``MAX_WORK_PER_CLAIM`` items in one transaction, each behind a compare-and-set, and
returns them: resumes first, then held questions never started, then the oldest
starts, then wakes. A row that has had ``MAX_AUTOMATIC_STARTS`` is not handed out:
a question moves to ``waiting_on_pm`` as ``starts_exhausted`` and an answer is recorded
``refused``, so no row is started for ever.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from amoeba.answering.values import DeclineReason
from amoeba.config.user_config import UserConfig
from amoeba.operations.steps.context import StepContext
from amoeba.operations.steps.limits import (
    MAX_AUTOMATIC_STARTS,
    MAX_WORK_PER_CLAIM,
    pause_claim_seconds,
    resume_claim_seconds,
    wake_limits,
)
from amoeba.operations.steps.models_work import (
    ClaimWorkReply,
    ClaimWorkRequest,
    HandlePauseItem,
    ResumeItem,
    WakeItem,
    WorkItem,
)
from amoeba.operations.steps.resume import ResumeClaimed, claim_resume
from amoeba.store.answers import record_resume
from amoeba.store.held_questions import mark_start_attempted, settle_held_waiting
from amoeba.store.machines import acting_machine_id, acting_machine_name
from amoeba.store.models import QuestionRecord
from amoeba.store.questions import settle_waiting
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import QuestionState, ResumeOutcome
from amoeba.store.wakes import WakeScope, claim_wake, wake_due
from amoeba.store.work import (
    ResumeWork,
    count_resume_start,
    dead_claim_work,
    held_work,
    resume_work,
    wake_candidates,
)

#: The name of ``wake`` logs under a machine's logs directory (D8).
WAKE_LOG_DIRECTORY = "wake"


def work_waiting(
    transaction: Transaction, machine_id: int, config: UserConfig, now: datetime
) -> bool:
    """Whether the machine has work waiting: any of D10's four kinds."""
    if resume_work(transaction, machine_id, now, resume_claim_seconds(config)):
        return True
    wait = float(config.answering_wait_seconds)
    if held_work(transaction, machine_id, now, wait):
        return True
    if dead_claim_work(transaction, machine_id, now, pause_claim_seconds(config), wait):
        return True
    limits = wake_limits(config)
    return any(
        wake_due(transaction, member, now, limits, WakeScope.ACTING_MACHINE)
        for member in wake_candidates(transaction, machine_id, now)
    )


def claim_work(context: StepContext, request: ClaimWorkRequest) -> ClaimWorkReply:
    """The step ``claim_work``: claim what the calling machine has waiting."""
    config = context.require_config()
    transaction = context.transaction
    machine_id = acting_machine_id(transaction)
    items: list[WorkItem] = []
    _claim_resumes(context, config, machine_id, items)
    _claim_pauses(context, config, machine_id, items)
    _claim_wakes(context, config, machine_id, Path(request.logs_dir), items)
    return ClaimWorkReply(items=tuple(items))


def _room(items: list[WorkItem]) -> bool:
    return len(items) < MAX_WORK_PER_CLAIM


def _claim_resumes(
    context: StepContext, config: UserConfig, machine_id: int, items: list[WorkItem]
) -> None:
    transaction, now = context.transaction, context.now
    limit = resume_claim_seconds(config)
    for work in resume_work(transaction, machine_id, now, limit):
        if work.start_count >= MAX_AUTOMATIC_STARTS:
            _refuse_resume(context, work)
            continue
        if not _room(items):
            return
        claim = claim_resume(transaction, work.answer_seq, now, limit)
        if not isinstance(claim, ResumeClaimed):
            continue
        count_resume_start(transaction, work.answer_seq)
        items.append(
            ResumeItem(
                answer_seq=work.answer_seq, claim_id=claim.claim_id, run_id=work.run_id
            )
        )


def _refuse_resume(context: StepContext, work: ResumeWork) -> None:
    """An answer whose attempts recorded no outcome is ``refused``, with the count."""
    detail = (
        f"{work.start_count} automatic resumes were started and no attempt recorded "
        "an outcome"
    )
    record_resume(
        context.transaction,
        work.answer_seq,
        ResumeOutcome.REFUSED,
        detail=detail,
        log=None,
        at=context.now,
        claim_id=None,
    )


def _claim_pauses(
    context: StepContext, config: UserConfig, machine_id: int, items: list[WorkItem]
) -> None:
    transaction, now = context.transaction, context.now
    wait = float(config.answering_wait_seconds)
    held = held_work(transaction, machine_id, now, wait)
    dead = dead_claim_work(
        transaction, machine_id, now, pause_claim_seconds(config), wait
    )
    never_started = [row for row in held if row.start_attempted_at is None]
    rest = sorted(
        [row for row in held if row.start_attempted_at is not None] + list(dead),
        key=lambda row: row.start_attempted_at or row.claimed_at,
    )
    for row in (*never_started, *rest):
        if row.start_count >= MAX_AUTOMATIC_STARTS:
            _exhaust_start(context, row)
            continue
        if not _room(items):
            return
        marked = mark_start_attempted(
            transaction, row.key, now, row.start_attempted_at, row.state
        )
        if marked:
            items.append(HandlePauseItem(run_id=row.key.run_id, checkout=row.checkout))


def _exhaust_start(context: StepContext, row: QuestionRecord) -> None:
    """A question that has had its automatic starts waits on the PM as
    ``starts_exhausted``, with the count and a pointer to the calls log of the machine
    the starts ran on."""
    transaction = context.transaction
    machine = acting_machine_name(transaction)
    detail = (
        f"{row.start_count} automatic starts of handle-pause did not settle this "
        f"question; the errors are in the calls log of {machine}"
    )
    if row.state is QuestionState.WAITING_ON_REQUEST:
        settle_held_waiting(
            transaction,
            row.key,
            reason=DeclineReason.STARTS_EXHAUSTED,
            detail=detail,
            now=context.now,
        )
    elif row.answering_run_id is not None:
        settle_waiting(
            transaction,
            row.key,
            row.answering_run_id,
            reason=DeclineReason.STARTS_EXHAUSTED,
            detail=detail,
            evidence=None,
            now=context.now,
        )


def _claim_wakes(
    context: StepContext,
    config: UserConfig,
    machine_id: int,
    logs_dir: Path,
    items: list[WorkItem],
) -> None:
    transaction, now = context.transaction, context.now
    limits = wake_limits(config)
    for member in wake_candidates(transaction, machine_id, now):
        if not _room(items):
            return
        wake_id = uuid4().hex
        log_stem = str(logs_dir / WAKE_LOG_DIRECTORY / wake_id)
        wake = claim_wake(transaction, member, now, limits, wake_id, log_stem)
        if wake is None:
            continue
        if wake.directory is None or wake.log_stem is None:
            raise AssertionError("a claimed wake has a directory and a log stem")
        items.append(
            WakeItem(
                wake_id=wake.wake_id, directory=wake.directory, log_stem=wake.log_stem
            )
        )
