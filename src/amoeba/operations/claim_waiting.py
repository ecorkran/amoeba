"""Recording why a claim path stopped: the question waits on the PM (slices 223, 242).

Three moves, one per kind of row: a new question is inserted ``waiting_on_pm``; a dead
claim is settled from ``claimed``; a held question is settled from
``waiting_on_request`` (242 D6). Each is one step, itself a compare-and-set, so a lost
race returns ``skipped`` or ``superseded`` and writes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from amoeba.answering.values import DeclineReason
from amoeba.operations.pause_context import PauseContext
from amoeba.operations.pause_models import HandlePauseResult, SkipReason
from amoeba.operations.pause_results import (
    PauseTarget,
    skipped,
    superseded_result,
    waiting_result,
)
from amoeba.operations.steps.models import QUESTION_INSERT, QUESTION_WAIT
from amoeba.operations.steps.models_pause import (
    QuestionInsertRequest,
    QuestionWaitRequest,
    passages_to_models,
)
from amoeba.operations.store_steps import Steps


@dataclass(frozen=True)
class ClaimFailed:
    """Why a claim path stopped before an answering run could settle."""

    reason: DeclineReason
    detail: str
    #: What was gathered before the failure, when anything was.
    context: PauseContext | None


def record_waiting(
    steps: Steps, target: PauseTarget, failed: ClaimFailed
) -> HandlePauseResult:
    """Insert the question as ``waiting_on_pm`` with the failure that stopped it."""
    context = failed.context
    inserted = steps.run(
        QUESTION_INSERT,
        QuestionInsertRequest(
            run_id=target.key.run_id,
            paused_at=target.key.paused_at,
            member_id=target.member.project_id,
            question=target.question,
            checkout=str(target.checkout),
            slice_label=None if context is None else context.slice_label,
            source_commit=None if context is None else context.source_commit,
            passages=None if context is None else passages_to_models(context.refs),
            answering_run_id=None,
            waiting_reason=failed.reason,
            waiting_detail=failed.detail,
        ),
    )
    if not inserted.inserted:
        return skipped(SkipReason.ALREADY_CLAIMED, target.key, str(target.checkout))
    return waiting_result(target, failed.reason, failed.detail, None)


def _wait(
    steps: Steps, target: PauseTarget, answering_run_id: str | None, failed: ClaimFailed
) -> bool:
    """Move the named claim (or, with no run id, the held row) to ``waiting_on_pm``;
    False when it was no longer that."""
    moved = steps.run(
        QUESTION_WAIT,
        QuestionWaitRequest(
            run_id=target.key.run_id,
            paused_at=target.key.paused_at,
            answering_run_id=answering_run_id,
            reason=failed.reason,
            detail=failed.detail,
            evidence=None,
        ),
    )
    return moved.applied


def settle_dead_claim_waiting(
    steps: Steps,
    target: PauseTarget,
    old_answering_run_id: str,
    failed: ClaimFailed,
) -> HandlePauseResult:
    """A dead claim whose context cannot be gathered again waits on the PM."""
    if not _wait(steps, target, old_answering_run_id, failed):
        return superseded_result(target, old_answering_run_id)
    return waiting_result(target, failed.reason, failed.detail, old_answering_run_id)


def settle_held(
    steps: Steps,
    target: PauseTarget,
    request_id: str,
    failed: ClaimFailed,
) -> HandlePauseResult:
    """A held question waits on the PM (242 D4, D6); ``superseded`` when it was no
    longer held."""
    if not _wait(steps, target, None, failed):
        return with_request(superseded_result(target, None), request_id)
    result = waiting_result(target, failed.reason, failed.detail, None)
    return with_request(result, request_id)


def with_request(result: HandlePauseResult, request_id: str) -> HandlePauseResult:
    """``result`` naming the request the question waits on or came from."""
    return replace(result, request_id=request_id)
