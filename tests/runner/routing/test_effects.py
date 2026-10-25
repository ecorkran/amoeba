"""``effect_for``: one case per row of D5's table."""

from __future__ import annotations

import pytest

from amoeba.runner.routing.engine import (
    PAYLOAD_JUDGE_ELIGIBLE,
    PAYLOAD_RULE_ID,
    PAYLOAD_TABLE_VERSION,
    REASON_ROUTED,
    effect_for,
    evaluate,
)
from amoeba.runner.routing.inputs import RoutingInputs
from amoeba.store import BlockEffect, NodeStatus, StatusEffect
from runner.routing.inputs_support import make_inputs
from runner.routing.table_support import small_table

RULES = """\
- id: advance-pass
  when: {outcome: completed, verdict: pass}
  route: advance
- id: rerun-concerns
  when: {outcome: completed, verdict: concerns}
  route: rerun
  max_attempts: 2
- id: escalate-fail
  when: {outcome: completed, verdict: fail}
  route: escalate
  judge_eligible: true
"""
RUN_ID = "run-20261025-p4-aaaa0001"
TABLE = small_table(RULES)


def _effect(inputs: RoutingInputs) -> StatusEffect | BlockEffect | None:
    match = evaluate(TABLE, inputs)
    return effect_for(match, inputs, table_version=TABLE.version, run_id=RUN_ID)


def test_advance_marks_the_step_done() -> None:
    assert _effect(make_inputs(verdict="pass")) == StatusEffect(NodeStatus.DONE)


def test_rerun_has_no_effect() -> None:
    assert _effect(make_inputs(verdict="concerns")) is None


def test_escalate_on_a_runnable_node_blocks_with_the_routed_payload() -> None:
    effect = _effect(make_inputs(verdict="fail"))
    assert effect == BlockEffect(
        context="routed by escalate-fail",
        payload={
            "reason": REASON_ROUTED,
            PAYLOAD_RULE_ID: "escalate-fail",
            PAYLOAD_TABLE_VERSION: TABLE.version,
            "run_id": RUN_ID,
            PAYLOAD_JUDGE_ELIGIBLE: True,
        },
    )


def test_the_block_payload_carries_judge_eligible_from_the_rule() -> None:
    effect = _effect(make_inputs(outcome="failed"))
    assert isinstance(effect, BlockEffect)
    assert effect.payload is not None
    assert effect.payload[PAYLOAD_JUDGE_ELIGIBLE] is False
    assert effect.payload[PAYLOAD_RULE_ID] == "catch-all"


@pytest.mark.parametrize("node_state", ["blocked", "done", "unknown"])
def test_escalate_on_a_node_that_is_not_runnable_has_no_effect(
    node_state: str,
) -> None:
    assert _effect(make_inputs(outcome="paused", node_state=node_state)) is None
