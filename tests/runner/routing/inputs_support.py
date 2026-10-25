"""Hand-built routing inputs for engine, effect and stage tests."""

from __future__ import annotations

from amoeba.runner.routing.inputs import NONE, RoutingInput, RoutingInputs

#: A completed run on a runnable ``slice_design`` step with no review.
BASE_VALUES = {
    RoutingInput.OUTCOME: "completed",
    RoutingInput.CHECKPOINT_KIND: NONE,
    RoutingInput.AT_LOOP: NONE,
    RoutingInput.FAILURE_KIND: NONE,
    RoutingInput.VERDICT: NONE,
    RoutingInput.STANDING: NONE,
    RoutingInput.SEVERITY: NONE,
    RoutingInput.RECURRENCE: NONE,
    RoutingInput.STEP: "slice_design",
    RoutingInput.NODE_STATE: "runnable",
}


def make_inputs(attempt: int | None = 1, **values: str) -> RoutingInputs:
    """``BASE_VALUES`` with the named inputs replaced (``verdict="pass"``)."""
    merged = dict(BASE_VALUES)
    for name, value in values.items():
        merged[RoutingInput(name)] = value
    return RoutingInputs(merged, attempt)
