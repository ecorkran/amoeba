"""D3: ``gate_state`` and ``check_standing`` reduced from the observation and checks."""

from __future__ import annotations

import pytest

from amoeba.runner.gates.cf_status import GatePosition
from amoeba.runner.gates.outcome_record import GATE_POSITION, GATE_STATUS
from amoeba.runner.routing.inputs import NONE, UNKNOWN, RoutingInput
from amoeba.store import CheckStanding
from runner.routing.evidence_support import completed_evidence, value


def _gate(position: GatePosition, status: str) -> dict[str, object]:
    return {GATE_POSITION: position.name, GATE_STATUS: status}


@pytest.mark.parametrize(
    ("step", "gate", "expected"),
    [
        (
            "slice_design",
            _gate(GatePosition.AT_SLICE_GATE, "pending-review"),
            "pending_review",
        ),
        (
            "slice_design",
            _gate(GatePosition.AT_SLICE_GATE, "review-failed"),
            "review_failed",
        ),
        ("slice_design", _gate(GatePosition.PAST_SLICE_GATE, "needs-tasks"), "clear"),
        ("tasks", _gate(GatePosition.PAST_TASKS_GATE, "in-implementation"), "clear"),
        ("tasks", _gate(GatePosition.AT_TASKS_GATE, "review-failed"), "review_failed"),
        ("implementation", _gate(GatePosition.PAST_CODE_GATE, "complete"), "clear"),
        (
            "implementation",
            _gate(GatePosition.PAST_TASKS_GATE, "in-implementation"),
            "misplaced",
        ),
        (
            "slice_design",
            _gate(GatePosition.PENDING_DECISION, "pending-decision"),
            "pending_decision",
        ),
        ("slice_design", {"failure": "cf exited 1"}, "unknown"),
        ("slice_design", None, "unknown"),
    ],
)
def test_gate_state_follows_the_step_s_exit_gate(
    step: str, gate: dict[str, object] | None, expected: str
) -> None:
    evidence = completed_evidence(step=step, gate_record=gate)

    assert value(evidence, RoutingInput.GATE_STATE) == expected


def test_gate_state_is_unknown_for_a_step_with_no_exit_gate() -> None:
    evidence = completed_evidence(step="merge", gate_record=None)

    assert value(evidence, RoutingInput.GATE_STATE) == UNKNOWN


def test_gate_state_is_unknown_for_an_unknown_step() -> None:
    evidence = completed_evidence(step=None, gate_record=None)

    assert value(evidence, RoutingInput.GATE_STATE) == UNKNOWN


@pytest.mark.parametrize(
    "overrides",
    [
        {"outcome": "failed"},
        {"outcome": "paused"},
        {"outcome": "orphaned"},
        {"outcome": "vanished"},
        {"outcome": "completed", "launch_failed": True},
        {"outcome": "completed", "resume_failed": True},
    ],
)
def test_both_inputs_are_none_for_an_outcome_that_is_not_completed(
    overrides: dict[str, object],
) -> None:
    evidence = completed_evidence(**overrides)

    assert value(evidence, RoutingInput.GATE_STATE) == NONE
    assert value(evidence, RoutingInput.CHECK_STANDING) == NONE


@pytest.mark.parametrize(
    ("standings", "expected"),
    [
        ((CheckStanding.PASSED, CheckStanding.PASSED), "passed"),
        ((CheckStanding.PASSED, CheckStanding.UNATTESTED), "unattested"),
        ((CheckStanding.UNATTESTED, CheckStanding.VACUOUS), "vacuous"),
        ((CheckStanding.VACUOUS, CheckStanding.ERRORED), "errored"),
        ((CheckStanding.ERRORED, CheckStanding.FAILED), "failed"),
        ((CheckStanding.PASSED, CheckStanding.FAILED), "failed"),
        ((CheckStanding.FAILED, CheckStanding.PASSED), "failed"),
        ((CheckStanding.PASSED, None), "unknown"),
        ((None, None), "unknown"),
        ((), "unknown"),
        (None, "unknown"),
    ],
)
def test_check_standing_is_the_worst_standing_or_unknown(
    standings: tuple[CheckStanding | None, ...] | None, expected: str
) -> None:
    evidence = completed_evidence(check_standings=standings)

    assert value(evidence, RoutingInput.CHECK_STANDING) == expected
