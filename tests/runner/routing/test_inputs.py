"""The routing vocabulary: closed sets and the inputs record's validation."""

from __future__ import annotations

import pytest

from amoeba.runner.routing.inputs import (
    NONE,
    UNKNOWN,
    VALUE_SETS,
    RoutingInput,
    RoutingInputs,
)

KNOWN_VALUES = {
    RoutingInput.OUTCOME: "completed",
    RoutingInput.CHECKPOINT_KIND: NONE,
    RoutingInput.AT_LOOP: NONE,
    RoutingInput.FAILURE_KIND: NONE,
    RoutingInput.VERDICT: "pass",
    RoutingInput.STANDING: "stated",
    RoutingInput.SEVERITY: "pass",
    RoutingInput.RECURRENCE: "clear",
    RoutingInput.STEP: "slice_design",
    RoutingInput.NODE_STATE: "runnable",
}


def test_every_input_has_a_value_set() -> None:
    assert set(VALUE_SETS) == set(RoutingInput)


@pytest.mark.parametrize("name", list(RoutingInput))
def test_every_set_contains_unknown(name: RoutingInput) -> None:
    assert UNKNOWN in VALUE_SETS[name]


def test_inputs_hold_the_values_given() -> None:
    inputs = RoutingInputs(KNOWN_VALUES, attempt=1)
    assert inputs.values[RoutingInput.VERDICT] == "pass"
    assert inputs.attempt == 1


def test_inputs_accept_a_null_attempt() -> None:
    assert RoutingInputs(KNOWN_VALUES, attempt=None).attempt is None


def test_inputs_refuse_a_missing_input() -> None:
    values = {k: v for k, v in KNOWN_VALUES.items() if k is not RoutingInput.STEP}
    with pytest.raises(ValueError, match="step"):
        RoutingInputs(values, attempt=1)


def test_inputs_refuse_an_out_of_set_value() -> None:
    values = {**KNOWN_VALUES, RoutingInput.VERDICT: "maybe"}
    with pytest.raises(ValueError, match="verdict.*maybe"):
        RoutingInputs(values, attempt=1)


def test_inputs_are_not_mutable_through_the_source_mapping() -> None:
    source = dict(KNOWN_VALUES)
    inputs = RoutingInputs(source, attempt=1)
    source[RoutingInput.VERDICT] = "fail"
    assert inputs.values[RoutingInput.VERDICT] == "pass"
