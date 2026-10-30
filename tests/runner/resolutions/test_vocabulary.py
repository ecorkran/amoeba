"""The resolution vocabulary is exactly what the design's tables say (D6)."""

from __future__ import annotations

import pytest

from amoeba.runner.faults import ResumeFailure
from amoeba.runner.resolutions.vocabulary import (
    ALLOWED,
    Continuation,
    ResolutionDecision,
    ResolutionRejection,
    Situation,
)

D = ResolutionDecision


@pytest.mark.parametrize(
    ("situation", "allowed"),
    [
        (Situation.RUN_TO_RESUME, {D.RESUME, D.STOP}),
        (Situation.NO_RUN, {D.RESUME, D.STOP}),
        (Situation.UNRESOLVABLE, set[D]()),
    ],
)
def test_allowed_matches_the_design_row_for_row(
    situation: Situation, allowed: set[D]
) -> None:
    assert ALLOWED[situation] == allowed


def test_every_situation_has_a_row() -> None:
    assert set(ALLOWED) == set(Situation)


def test_the_vocabularies_hold_exactly_the_documented_values() -> None:
    assert {d.value for d in ResolutionDecision} == {"resume", "stop"}
    assert {s.value for s in Situation} == {"run_to_resume", "no_run", "unresolvable"}
    assert {c.value for c in Continuation} == {"resume"}
    assert {r.value for r in ResolutionRejection} == {
        "unknown_decision",
        "decision_required",
        "instructions_not_applicable",
        "unresolvable",
    }
    assert {f.value for f in ResumeFailure} == {
        "refused",
        "exited_before_claim",
        "no_claim_within_grace",
        "spawn_error",
        "run_missing",
    }
