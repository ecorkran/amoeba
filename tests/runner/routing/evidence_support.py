"""Hand-built routing evidence for the reducer's table-driven tests."""

from __future__ import annotations

from dataclasses import replace

from amoeba.runner.routing.inputs import RoutingInput
from amoeba.runner.routing.reduce import OutcomeEvidence, ReviewPart, reduce
from amoeba.store import (
    FindingChange,
    FindingSeverity,
    NodeStatus,
    ReviewVerdict,
    VerdictStanding,
)


def part(
    verdict: ReviewVerdict = ReviewVerdict.PASS,
    standing: VerdictStanding = VerdictStanding.STATED,
    severity: FindingSeverity = FindingSeverity.PASS,
    *,
    comparable: bool = True,
    changes: tuple[FindingChange, ...] = (),
) -> ReviewPart:
    return ReviewPart(verdict, standing, severity, comparable, changes)


def completed_evidence(**changes: object) -> OutcomeEvidence:
    """A completed run on a runnable ``slice_design`` step with no review."""
    base = OutcomeEvidence(
        outcome="completed",
        launch_failed=False,
        resume_failed=False,
        continuation=None,
        verdict_ids=(),
        continued_verdict_ids=None,
        checkpoint=None,
        failure=None,
        step="slice_design",
        node_status=NodeStatus.RUNNABLE,
        attempt_count=0,
        review_fault=False,
        review_unreadable=False,
        parts=(),
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def value(evidence: OutcomeEvidence, name: RoutingInput) -> str:
    return reduce(evidence).values[name]
