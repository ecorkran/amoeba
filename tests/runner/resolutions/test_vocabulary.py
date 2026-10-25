"""The resolution vocabulary is exactly what the design's tables say (D2, D3)."""

from __future__ import annotations

import pytest

from amoeba.process import CheckpointKind
from amoeba.runner.faults import ResumeFailure
from amoeba.runner.resolutions.vocabulary import (
    ALLOWED,
    Continuation,
    ResolutionDecision,
    ResolutionRejection,
    Situation,
)
from amoeba.runner.routing.inputs import VALUE_SETS, RoutingInput

D = ResolutionDecision


@pytest.mark.parametrize(
    ("situation", "allowed"),
    [
        (Situation.NO_DECISION, set[D]()),
        (Situation.PAUSED_RUN, {D.RETRY, D.ACCEPT, D.HANDLED, D.STOP}),
        (Situation.COMPLETED_OUTCOME, {D.ACCEPT, D.RERUN, D.STOP}),
        (Situation.ENDED_RUN, {D.RERUN, D.STOP}),
        (Situation.BEFORE_RUN, {D.RERUN, D.STOP}),
        (Situation.UNRESOLVABLE, set[D]()),
    ],
)
def test_allowed_matches_the_design_row_for_row(
    situation: Situation, allowed: set[D]
) -> None:
    assert ALLOWED[situation] == allowed


def test_every_situation_has_a_row() -> None:
    assert set(ALLOWED) == set(Situation)


@pytest.mark.parametrize("situation", [Situation.UNRESOLVABLE, Situation.NO_DECISION])
def test_unresolvable_and_no_decision_allow_nothing(situation: Situation) -> None:
    assert ALLOWED[situation] == frozenset()


def test_the_vocabularies_hold_exactly_the_documented_values() -> None:
    assert {d.value for d in ResolutionDecision} == {
        "retry",
        "accept",
        "handled",
        "rerun",
        "stop",
    }
    assert {c.value for c in Continuation} == {"retry", "accept", "observe"}
    assert {f.value for f in ResumeFailure} == {
        "refused",
        "exited_before_claim",
        "no_claim_within_grace",
        "spawn_error",
        "run_missing",
    }
    assert len(ResolutionRejection) == 9


def test_routing_knows_the_usage_limit_checkpoint() -> None:
    assert CheckpointKind.USAGE_LIMIT.value == "usage_limit"
    assert "usage_limit" in VALUE_SETS[RoutingInput.CHECKPOINT_KIND]
