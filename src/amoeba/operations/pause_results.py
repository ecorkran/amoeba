"""Results of the pause paths: skipped, waiting, superseded, resumed (slice 223).

``finish`` turns a settle into a ``HandlePauseResult``, resuming the run only for an
``answered`` question; ``resume_answer`` is the one place a recorded answer is handed
back and reported; ``skipped`` is a call that left the pause alone. ``PauseTarget`` is
the pause a call is handling, shared by the claim and existing-row paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from amoeba.answering.values import DeclineReason
from amoeba.config.user_config import UserConfig
from amoeba.operations.answering_settle import (
    SettleResult,
    Superseded,
    Waiting,
)
from amoeba.operations.deps import Deps
from amoeba.operations.pause_models import (
    HandlePauseOutcome,
    HandlePauseResult,
    SkipReason,
)
from amoeba.operations.resume import resume
from amoeba.store.models import Member, QuestionKey
from amoeba.store.questions import get_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ResumeOutcome
from amoeba.upstream.squadron.run_file import RunFacts


@dataclass(frozen=True)
class PauseTarget:
    """The pause a call is handling: what both claim paths need."""

    key: QuestionKey
    #: The question text exactly as Squadron printed it.
    question: str
    #: The checkout the question is claimed in.
    checkout: Path
    member: Member
    run_facts: RunFacts


def waiting_result(
    target: PauseTarget,
    reason: DeclineReason,
    detail: str | None,
    answering_run_id: str | None,
) -> HandlePauseResult:
    """A question left waiting on the PM, with why."""
    return HandlePauseResult(
        HandlePauseOutcome.WAITING_ON_PM,
        waiting_reason=reason,
        detail=detail,
        key=target.key,
        checkout=str(target.checkout),
        answering_run_id=answering_run_id,
    )


def superseded_result(
    target: PauseTarget, answering_run_id: str | None
) -> HandlePauseResult:
    """A claim that was no longer this caller's when it tried to settle it."""
    return HandlePauseResult(
        HandlePauseOutcome.SUPERSEDED,
        key=target.key,
        checkout=str(target.checkout),
        answering_run_id=answering_run_id,
    )


def finish(  # noqa: PLR0913 - what a settled claim needs to become a result
    store: Store,
    config: UserConfig,
    deps: Deps,
    target: PauseTarget,
    answering_run_id: str,
    settled: SettleResult,
) -> HandlePauseResult:
    """A settle as a result: resume the run only when the question was answered."""
    if isinstance(settled, Superseded):
        return superseded_result(target, answering_run_id)
    if isinstance(settled, Waiting):
        return waiting_result(target, settled.reason, settled.detail, answering_run_id)
    return resume_answer(
        store, config, deps, target.key, settled.answer_seq, answering_run_id
    )


def resume_answer(  # noqa: PLR0913 - the pieces of one resume
    store: Store,
    config: UserConfig,
    deps: Deps,
    key: QuestionKey,
    answer_seq: int,
    answering_run_id: str | None,
) -> HandlePauseResult:
    """Resume the question's run with the answer and report it as a result."""
    with store.read() as transaction:
        record = get_question(transaction, key)
    if record is None:
        raise ValueError(f"no question {key} to resume")
    resumed = resume(
        store,
        record,
        answer_seq,
        deps=deps,
        wait_seconds=config.resume_wait_seconds,
    )
    return HandlePauseResult(
        _OUTCOME_OF_RESUME[resumed.outcome],
        detail=resumed.detail,
        key=key,
        checkout=record.checkout,
        answering_run_id=answering_run_id,
        answer_seq=answer_seq,
    )


_OUTCOME_OF_RESUME = {
    ResumeOutcome.RESUMED: HandlePauseOutcome.RESUMED,
    ResumeOutcome.REFUSED: HandlePauseOutcome.REFUSED,
    ResumeOutcome.NOT_DELIVERED: HandlePauseOutcome.NOT_DELIVERED,
}


def skipped(
    reason: SkipReason,
    key: QuestionKey | None,
    checkout: str | None,
    detail: str | None = None,
) -> HandlePauseResult:
    """A call that left the pause alone."""
    return HandlePauseResult(
        HandlePauseOutcome.SKIPPED,
        skip_reason=reason,
        detail=detail,
        key=key,
        checkout=checkout,
    )
