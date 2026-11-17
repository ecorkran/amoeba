"""Recording why a claim path stopped: the question waits on the PM (slices 223, 242).

Three moves, one per kind of row: a new question is inserted ``waiting_on_pm``; a dead
claim is settled from ``claimed``; a held question is settled from
``waiting_on_request`` (242 D6). Each is a compare-and-set, so a lost race returns
``skipped`` or ``superseded`` and writes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from amoeba.answering.values import DeclineReason
from amoeba.operations.deps import Deps
from amoeba.operations.pause_context import PauseContext
from amoeba.operations.pause_models import HandlePauseResult, SkipReason
from amoeba.operations.pause_results import (
    PauseTarget,
    skipped,
    superseded_result,
    waiting_result,
)
from amoeba.store.held_questions import settle_held_waiting
from amoeba.store.questions import NewQuestion, insert_question, settle_waiting
from amoeba.store.store import Store


@dataclass(frozen=True)
class ClaimFailed:
    """Why a claim path stopped before an answering run could settle."""

    reason: DeclineReason
    detail: str
    #: What was gathered before the failure, when anything was.
    context: PauseContext | None


def record_waiting(
    store: Store, deps: Deps, target: PauseTarget, failed: ClaimFailed
) -> HandlePauseResult:
    """Insert the question as ``waiting_on_pm`` with the failure that stopped it."""
    context = failed.context
    new = NewQuestion(
        key=target.key,
        member_id=target.member.project_id,
        question=target.question,
        checkout=str(target.checkout),
        slice_label=None if context is None else context.slice_label,
        source_commit=None if context is None else context.source_commit,
        passages=None if context is None else context.refs,
        answering_run_id=None,
        waiting_reason=failed.reason,
        waiting_detail=failed.detail,
    )
    with store.write() as transaction:
        inserted = insert_question(transaction, new, now=deps.clock())
    if not inserted:
        return skipped(SkipReason.ALREADY_CLAIMED, target.key, str(target.checkout))
    return waiting_result(target, failed.reason, failed.detail, None)


def settle_dead_claim_waiting(
    store: Store,
    deps: Deps,
    target: PauseTarget,
    old_answering_run_id: str,
    failed: ClaimFailed,
) -> HandlePauseResult:
    """A dead claim whose context cannot be gathered again waits on the PM."""
    with store.write() as transaction:
        moved = settle_waiting(
            transaction,
            target.key,
            old_answering_run_id,
            reason=failed.reason,
            detail=failed.detail,
            evidence=None,
            now=deps.clock(),
        )
    if not moved:
        return superseded_result(target, old_answering_run_id)
    return waiting_result(target, failed.reason, failed.detail, old_answering_run_id)


def settle_held(
    store: Store,
    deps: Deps,
    target: PauseTarget,
    request_id: str,
    failed: ClaimFailed,
) -> HandlePauseResult:
    """A held question waits on the PM (242 D4, D6); ``superseded`` when it was no
    longer held."""
    with store.write() as transaction:
        moved = settle_held_waiting(
            transaction,
            target.key,
            reason=failed.reason,
            detail=failed.detail,
            now=deps.clock(),
        )
    if not moved:
        return with_request(superseded_result(target, None), request_id)
    result = waiting_result(target, failed.reason, failed.detail, None)
    return with_request(result, request_id)


def with_request(result: HandlePauseResult, request_id: str) -> HandlePauseResult:
    """``result`` naming the request the question waits on or came from."""
    return replace(result, request_id=request_id)
