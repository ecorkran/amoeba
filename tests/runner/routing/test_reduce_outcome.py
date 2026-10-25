"""D1's reductions for the six outcome inputs, over hand-built evidence."""

from __future__ import annotations

import pytest

from amoeba.process.sq_outcome import (
    CheckpointKind,
    FailureKind,
    RunCheckpoint,
    RunFailure,
    RunOutcome,
)
from amoeba.runner.ingest.record import OUTCOME_VANISHED
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.routing.inputs import (
    NONE,
    OUTCOME_LAUNCH_FAILED,
    UNKNOWN,
    RoutingInput,
)
from amoeba.runner.routing.reduce import reduce
from amoeba.store import NodeStatus
from runner.routing.evidence_support import completed_evidence, value

OUTCOME = RoutingInput.OUTCOME


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (RunOutcome.COMPLETED.value, "completed"),
        (RunOutcome.PAUSED.value, "paused"),
        (RunOutcome.FAILED.value, "failed"),
        (RunOutcome.ORPHANED.value, "orphaned"),
        (OUTCOME_VANISHED, "vanished"),
        (RunOutcome.TIMED_OUT.value, UNKNOWN),
        (RunOutcome.NOT_FOUND.value, UNKNOWN),
        ("from_the_future", UNKNOWN),
        (None, UNKNOWN),
    ],
)
def test_outcome_reduces_the_result_text(text: str | None, expected: str) -> None:
    assert value(completed_evidence(outcome=text), OUTCOME) == expected


def test_launch_failure_overrides_the_result_text() -> None:
    evidence = completed_evidence(outcome=None, launch_failed=True)
    assert value(evidence, OUTCOME) == OUTCOME_LAUNCH_FAILED


@pytest.mark.parametrize("kind", list(CheckpointKind))
def test_each_checkpoint_kind_reduces_to_itself(kind: CheckpointKind) -> None:
    evidence = completed_evidence(checkpoint=RunCheckpoint(kind=kind.value))
    assert value(evidence, RoutingInput.CHECKPOINT_KIND) == kind.value


@pytest.mark.parametrize(
    ("checkpoint", "expected"),
    [
        (None, NONE),
        (RunCheckpoint(kind=None), UNKNOWN),
        (RunCheckpoint(kind="a_newer_kind"), UNKNOWN),
    ],
)
def test_checkpoint_kind_absent_null_and_unrecognized(
    checkpoint: RunCheckpoint | None, expected: str
) -> None:
    evidence = completed_evidence(checkpoint=checkpoint)
    assert value(evidence, RoutingInput.CHECKPOINT_KIND) == expected


@pytest.mark.parametrize("kind", list(FailureKind))
def test_each_failure_kind_reduces_to_itself(kind: FailureKind) -> None:
    evidence = completed_evidence(failure=RunFailure(kind=kind.value))
    assert value(evidence, RoutingInput.FAILURE_KIND) == kind.value


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (None, NONE),
        (RunFailure(kind=None), UNKNOWN),
        (RunFailure(kind="a_newer_kind"), UNKNOWN),
    ],
)
def test_failure_kind_absent_null_and_unrecognized(
    failure: RunFailure | None, expected: str
) -> None:
    evidence = completed_evidence(failure=failure)
    assert value(evidence, RoutingInput.FAILURE_KIND) == expected


@pytest.mark.parametrize(
    ("is_loop", "expected"),
    [(True, "true"), (False, "false"), ("yes", UNKNOWN), (1, UNKNOWN), (None, UNKNOWN)],
)
def test_at_loop_reduces_only_a_json_boolean(is_loop: object, expected: str) -> None:
    checkpoint = RunCheckpoint(kind="loop_exhausted", is_loop=is_loop)  # type: ignore[arg-type]
    evidence = completed_evidence(checkpoint=checkpoint)
    assert value(evidence, RoutingInput.AT_LOOP) == expected


def test_at_loop_is_none_without_a_checkpoint() -> None:
    assert value(completed_evidence(), RoutingInput.AT_LOOP) == NONE


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (NodeStatus.RUNNABLE, "runnable"),
        (NodeStatus.DONE, "done"),
        (NodeStatus.BLOCKED_ON_HUMAN, "blocked"),
        (NodeStatus.BLOCKED_ON_JUDGE, "blocked"),
        (NodeStatus.BLOCKED_ON_SQ_CHECKPOINT, "blocked"),
        (NodeStatus.IN_PROGRESS, UNKNOWN),
    ],
)
def test_node_state_maps_every_status(status: NodeStatus, expected: str) -> None:
    evidence = completed_evidence(node_status=status)
    assert value(evidence, RoutingInput.NODE_STATE) == expected


@pytest.mark.parametrize("step", list(LifecycleStep))
def test_a_known_step_counts_the_next_attempt(step: LifecycleStep) -> None:
    inputs = reduce(completed_evidence(step=step.value, attempt_count=2))
    assert inputs.values[RoutingInput.STEP] == step.value
    assert inputs.attempt == 3


@pytest.mark.parametrize("step", [None, "a_phase_cf_invented"])
def test_an_unknown_step_has_no_attempt(step: str | None) -> None:
    inputs = reduce(completed_evidence(step=step, attempt_count=None))
    assert inputs.values[RoutingInput.STEP] == UNKNOWN
    assert inputs.attempt is None


def test_a_known_step_without_a_count_is_a_gather_bug() -> None:
    with pytest.raises(ValueError, match="attempts were not counted"):
        reduce(completed_evidence(attempt_count=None))
