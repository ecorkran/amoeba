"""``ingest``: block if a human must look, then record the reviews and resolve (D6).

The order is always the same and safe to repeat. A crash after the block leaves an
unresolved entry whose run still exists, so the next tick polls the run again and
repeats ``ingest``: the block is skipped because the node is already blocked, and
each verdict id is the review's parsed-content digest, so recording it again is
``record_verdict``'s retry, a no-op.

Reviews that cannot be recorded (D7's :class:`ReviewUnknown`) never fail the run's
ingestion. They add a block, or a ``review_fault`` to the block the outcome already
needs, and the entry still resolves and is left for routing.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final

from amoeba.process import RunOutcomeDocument
from amoeba.runner.faults import PAYLOAD_FAULT_KIND, FaultKind
from amoeba.runner.ingest.outcome import (
    BlockPlan,
    OutcomePlan,
    cut_to_bound,
    plan_outcome,
)
from amoeba.runner.ingest.reviews import (
    ReviewFiles,
    ReviewScope,
    ReviewUnknown,
    select_review_files,
)
from amoeba.runner.observed import RunEnded, RunVanished
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_RUN_ID,
    BlockedKind,
    JournalEntry,
    NodeKind,
    RunnerReview,
    Store,
)

#: Keys of the ``sq_run`` entry's result: 126's input for the run, and 127's source
#: for resuming a paused run.
RESULT_RUN_ID: Final = PARAM_RUN_ID
RESULT_OUTCOME: Final = "outcome"
RESULT_STATUS: Final = "status"
RESULT_OUTCOME_DOCUMENT: Final = "outcome_document"
RESULT_VERDICT_IDS: Final = "verdict_ids"
RESULT_REVIEW_FAULT: Final = "review_fault"

#: Block payload keys added by an unknown review.
PAYLOAD_PATH: Final = "path"
PAYLOAD_REASON_TEXT: Final = "reason"
PAYLOAD_REVIEW_FAULT: Final = "review_fault"

#: What the result says for a run Squadron no longer knows.
OUTCOME_VANISHED: Final = "vanished"


def ingest(
    store: Store,
    entry: JournalEntry,
    finished: RunEnded | RunVanished,
    version_label: str,
) -> None:
    """Block the node if needed, record the run's reviews, resolve the entry."""
    run_id = _run_id(entry)
    plan = plan_outcome(finished, run_id)
    reviews = _reviews(store, entry, finished, run_id, version_label)
    unknown: ReviewUnknown | None = None
    recorded: tuple[RunnerReview, ...] = ()
    if isinstance(reviews, ReviewUnknown):
        unknown = reviews
    else:
        recorded = reviews.reviews
    block = _block_with(plan, unknown)
    if block is not None:
        block_once(store, entry.node_id, block)
    store.record_runner_report(
        entry.id,
        recorded,
        outcome=plan.entry_outcome,
        result=_result(finished, run_id, [r.verdict.id for r in recorded], unknown),
    )


def block_once(store: Store, node_id: str, block: BlockPlan) -> None:
    """Block the node on ``block``, unless it is already blocked."""
    if store.blocked_state_for(node_id) is not None:
        return
    store.block(node_id, kind=block.kind, context=block.context, payload=block.payload)


def _block_with(plan: OutcomePlan, unknown: ReviewUnknown | None) -> BlockPlan | None:
    """The outcome's block, adjusted for a review that could not be recorded."""
    if unknown is None:
        return plan.block
    fault = {PAYLOAD_REVIEW_FAULT: cut_to_bound(unknown.reason)}
    block = plan.block
    if block is not None and block.kind is BlockedKind.HUMAN:
        # The outcome's own block stands, with the fault added to its payload.
        return BlockPlan(block.kind, block.context, {**(block.payload or {}), **fault})
    # No outcome block, or a checkpoint: a person must be told, and a checkpoint
    # block posts no message, so this is a HUMAN block either way.
    return BlockPlan(
        BlockedKind.HUMAN,
        f"review unknown: {cut_to_bound(unknown.reason)}",
        {
            PAYLOAD_FAULT_KIND: FaultKind.REVIEW_UNKNOWN.value,
            PAYLOAD_PATH: unknown.path,
            PAYLOAD_REASON_TEXT: cut_to_bound(unknown.reason),
        },
    )


def _reviews(
    store: Store,
    entry: JournalEntry,
    finished: RunEnded | RunVanished,
    run_id: str,
    version_label: str,
) -> ReviewFiles | ReviewUnknown:
    if isinstance(finished, RunVanished) or not finished.document.reviews:
        return ReviewFiles(())
    scope = _scope(store, entry, run_id, version_label)
    if isinstance(scope, ReviewUnknown):
        return scope
    return select_review_files(finished.document, scope)


def _scope(
    store: Store, entry: JournalEntry, run_id: str, version_label: str
) -> ReviewScope | ReviewUnknown:
    """What attribution needs: the checkout and the step's parent slice node."""
    checkout = entry.parameters.get(PARAM_CHECKOUT)
    if not isinstance(checkout, str) or not checkout:
        return ReviewUnknown(None, f"entry {entry.id} carries no checkout")
    step = store.get_node(entry.node_id)
    parent = (
        None
        if step is None or step.parent_id is None
        else store.get_node(step.parent_id)
    )
    if parent is None or parent.kind is not NodeKind.SLICE:
        return ReviewUnknown(None, f"the step node of entry {entry.id} has no slice")
    return ReviewScope(
        project_id=entry.project_id,
        run_id=run_id,
        checkout=Path(checkout),
        slice_node_id=parent.id,
        slice_nodes=store.nodes_for_project(entry.project_id),
        watches=store.watches(entry.project_id),
        version_label=version_label,
    )


def _result(
    finished: RunEnded | RunVanished,
    run_id: str,
    verdict_ids: list[str],
    unknown: ReviewUnknown | None,
) -> Mapping[str, object]:
    document: RunOutcomeDocument | None = (
        None if isinstance(finished, RunVanished) else finished.document
    )
    return {
        RESULT_RUN_ID: run_id,
        RESULT_OUTCOME: OUTCOME_VANISHED
        if document is None
        else document.outcome.value,
        RESULT_STATUS: None if document is None else document.status,
        RESULT_OUTCOME_DOCUMENT: (
            None if document is None else document.model_dump(mode="json")
        ),
        RESULT_VERDICT_IDS: verdict_ids,
        RESULT_REVIEW_FAULT: None if unknown is None else cut_to_bound(unknown.reason),
    }


def _run_id(entry: JournalEntry) -> str:
    run_id = entry.parameters.get(PARAM_RUN_ID)
    if not isinstance(run_id, str) or not run_id:
        raise ValueError(f"entry {entry.id} has an unusable run id: {run_id!r}")
    return run_id
