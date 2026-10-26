"""``recompute``: a decision is checked against its own stored table version."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from amoeba.runner.routing.engine import evaluate
from amoeba.runner.routing.inputs import INPUT_ATTEMPT, RoutingInputs
from amoeba.runner.routing.recompute import recompute
from amoeba.store import Route, RoutingDecision, RoutingTableVersion
from runner.routing.inputs_support import make_inputs
from runner.routing.table_support import small_table, table_text

RULES = """\
- id: advance-pass
  when: {outcome: completed, verdict: pass}
  route: advance
"""


STORED = RoutingTableVersion("sha256:x", table_text(RULES))
DECIDED_AT = datetime(2026, 10, 25, tzinfo=UTC)


def _decision(
    inputs: RoutingInputs, table_version: str, **changes: object
) -> RoutingDecision:
    table = small_table(RULES)
    match = evaluate(table, inputs)
    recorded = {name.value: value for name, value in inputs.values.items()}
    recorded[INPUT_ATTEMPT] = inputs.attempt  # type: ignore[assignment]
    base = RoutingDecision(
        id="d-1",
        project_id="demo",
        node_id="n-1",
        inputs=recorded,
        rule_id=match.rule.id,
        table_version=table_version,
        amoeba_version="0.1",
        route=match.route,
        route_parameters=match.parameters,
        decided_at=DECIDED_AT,
    )
    return dataclasses.replace(base, **changes)  # type: ignore[arg-type]


def test_decision_recomputes_from_stored_version() -> None:
    inputs = make_inputs(verdict="pass")
    result = recompute(_decision(inputs, "sha256:x"), STORED)
    assert result.error is None
    assert result.matches is True
    assert (result.rule_id, result.route) == ("advance-pass", Route.ADVANCE)


def test_a_decision_with_an_altered_rule_id_does_not_match() -> None:
    inputs = make_inputs(verdict="pass")
    decision = _decision(inputs, "sha256:x", rule_id="something-else")
    result = recompute(decision, STORED)
    assert result.error is None
    assert result.matches is False
    assert result.rule_id == "advance-pass"


def test_a_decision_with_an_altered_route_does_not_match() -> None:
    inputs = make_inputs(verdict="pass")
    decision = _decision(inputs, "sha256:x", route=Route.ESCALATE)
    assert recompute(decision, STORED).matches is False


def test_old_decisions_recompute_against_their_own_version() -> None:
    inputs = make_inputs(verdict="pass")
    decision = _decision(inputs, "sha256:x")
    newer = RoutingTableVersion("sha256:y", table_text())  # no advance rule
    assert recompute(decision, STORED).matches is True
    assert recompute(decision, newer).matches is False


def test_unparseable_stored_content_is_an_error_not_a_mismatch() -> None:
    decision = _decision(make_inputs(verdict="pass"), "sha256:x")
    result = recompute(decision, RoutingTableVersion("sha256:x", "rules: [unclosed"))
    assert result.error is not None and "not valid YAML" in result.error
    assert result.matches is False


def test_an_unsupported_format_is_an_error_not_a_mismatch() -> None:
    decision = _decision(make_inputs(verdict="pass"), "sha256:x")
    content = table_text(RULES).replace("format: 1", "format: 9")
    result = recompute(decision, RoutingTableVersion("sha256:x", content))
    assert result.error is not None and "format 9" in result.error


def test_inputs_outside_todays_vocabulary_are_an_error() -> None:
    decision = _decision(make_inputs(verdict="pass"), "sha256:x")
    broken = dataclasses.replace(
        decision, inputs={**decision.inputs, "verdict": "great"}
    )
    result = recompute(broken, STORED)
    assert result.error is not None and "verdict" in result.error


def test_a_missing_recorded_input_is_an_error() -> None:
    decision = _decision(make_inputs(verdict="pass"), "sha256:x")
    inputs = {k: v for k, v in decision.inputs.items() if k != "step"}
    result = recompute(dataclasses.replace(decision, inputs=inputs), STORED)
    assert result.error is not None and "step" in result.error


def test_a_null_attempt_recomputes() -> None:
    inputs = make_inputs(attempt=None, verdict="pass", step="unknown")
    result = recompute(_decision(inputs, "sha256:x"), STORED)
    assert result.error is None and result.matches is True


@pytest.mark.parametrize("missing", ["gate_state", "check_standing"])
def test_a_decision_recorded_before_slice_128_cannot_be_recomputed(
    missing: str,
) -> None:
    """Slice 128 added two inputs: an older record fails as a changed vocabulary."""
    decision = _decision(make_inputs(verdict="pass"), "sha256:x")
    inputs = {k: v for k, v in decision.inputs.items() if k != missing}

    result = recompute(dataclasses.replace(decision, inputs=inputs), STORED)

    assert result.matches is False
    assert result.error is not None and missing in result.error


def test_a_decision_recorded_before_review_accepted_existed_cannot_be_recomputed() -> (
    None
):
    """Slice 127 added an input: an older record fails as a changed vocabulary."""
    decision = _decision(make_inputs(verdict="pass"), "sha256:x")
    inputs = {k: v for k, v in decision.inputs.items() if k != "review_accepted"}

    result = recompute(dataclasses.replace(decision, inputs=inputs), STORED)

    assert result.matches is False
    assert result.error is not None and "review_accepted" in result.error
