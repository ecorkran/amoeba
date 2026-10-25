"""Stage an ingested outcome in a store: a resolved ``sq_run`` entry awaiting routing.

The result has the shape 125's ingestion leaves, so ``gather`` reads what it reads
in production. The run itself is not simulated; tick-level tests use the stub ``sq``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from evidence_harness import PROJECT, finding, verdict_input
from sq_run_fixtures import sq_run_parameters

from amoeba.process import RunOutcome
from amoeba.runner.finish import RESULT_LAUNCH_FAILURE
from amoeba.runner.ingest.record import (
    RESULT_OUTCOME,
    RESULT_OUTCOME_DOCUMENT,
    RESULT_REVIEW_FAULT,
    RESULT_RUN_ID,
    RESULT_STATUS,
    RESULT_VERDICT_IDS,
)
from amoeba.store import (
    CFReference,
    CommandKind,
    DetectionInput,
    DetectionOutcome,
    FindingInput,
    FindingSeverity,
    JournalEntry,
    JournalOutcome,
    NodeKind,
    ReviewVerdict,
    RunnerReview,
    Store,
)

#: Keys an ``sq_run`` entry must carry; their values here are inert.
_RUN_PARAMETERS: Mapping[str, object] = {
    "pipeline": "P4",
    "params": {},
    "project": "p",
    "expected": "x",
    "checkout": "/work/p",
}


@dataclass(frozen=True)
class StagedReview:
    """One verdict to record with the outcome."""

    verdict_id: str
    verdict: ReviewVerdict = ReviewVerdict.CONCERNS
    findings: Sequence[FindingInput] = field(default_factory=tuple)
    overrides: Mapping[str, object] = field(default_factory=dict[str, object])


def stage_node(store: Store, phase: str | None = "slice_design") -> str:
    """A slice-kind step node whose ``cf.phase`` is ``phase``."""
    return store.create_node(
        project_id=PROJECT,
        kind=NodeKind.SLICE,
        title="step",
        cf=CFReference(phase=phase),
    ).id


def stage_outcome(
    store: Store,
    node_id: str,
    *,
    run_id: str = "run-20261025-p4-aaaa0001",
    outcome: str = RunOutcome.COMPLETED.value,
    document: Mapping[str, object] | None = None,
    reviews: Sequence[StagedReview] = (),
    verdict_ids: Sequence[str] | None = None,
    review_fault: str | None = None,
    launch_failure: str | None = None,
) -> JournalEntry:
    """Issue an ``sq_run`` on ``node_id`` and resolve it as ingestion would."""
    issued = store.journal_issue(
        node_id,
        kind=CommandKind.SQ_RUN,
        parameters=sq_run_parameters(_RUN_PARAMETERS, run_id=run_id),
    )
    recorded = [_review(node_id, staged) for staged in reviews]
    result: dict[str, object] = {RESULT_RUN_ID: run_id}
    if launch_failure is not None:
        result[RESULT_LAUNCH_FAILURE] = launch_failure
    else:
        result.update(
            {
                RESULT_OUTCOME: outcome,
                RESULT_STATUS: outcome,
                RESULT_OUTCOME_DOCUMENT: document,
                RESULT_VERDICT_IDS: list(
                    verdict_ids
                    if verdict_ids is not None
                    else [staged.verdict_id for staged in reviews]
                ),
                RESULT_REVIEW_FAULT: review_fault,
            }
        )
    journal_outcome = (
        JournalOutcome.COMPLETED
        if outcome == RunOutcome.COMPLETED.value and launch_failure is None
        else JournalOutcome.FAILED
    )
    store.record_runner_report(
        issued.id, recorded, outcome=journal_outcome, result=result
    )
    staged_entry = store.journal_entry(issued.id)
    assert staged_entry is not None
    return staged_entry


def _review(node_id: str, staged: StagedReview) -> RunnerReview:
    verdict = verdict_input(
        staged.verdict_id,
        node_id,
        *staged.findings,
        verdict=staged.verdict,
        **staged.overrides,
    )
    detection = DetectionInput(
        project_id=PROJECT,
        path=f"/r/{staged.verdict_id}.md",
        digest=f"digest-{staged.verdict_id}",
        outcome=DetectionOutcome.RUNNER_ISSUED,
        record_id=staged.verdict_id,
    )
    return RunnerReview(verdict, detection)


def concern(summary: str) -> FindingInput:
    return finding(summary, severity=FindingSeverity.CONCERN)


def note(summary: str) -> FindingInput:
    return finding(summary, severity=FindingSeverity.NOTE)
