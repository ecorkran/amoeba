"""``evaluate``: first match wins, ``unknown`` is explicit, routes are restricted."""

from __future__ import annotations

from amoeba.runner.routing.engine import evaluate
from amoeba.store import Route
from runner.routing.inputs_support import make_inputs
from runner.routing.table_support import small_table

ADVANCE_ON_PASS = """\
- id: advance-pass
  when: {outcome: completed, verdict: pass}
  route: advance
"""

RERUN_ON_CONCERNS = """\
- id: rerun-concerns
  when: {outcome: completed, verdict: concerns, step: slice_design}
  route: rerun
  max_attempts: 2
"""

ESCALATE_CONCERNS = """\
- id: escalate-concerns
  when: {outcome: completed, verdict: concerns}
  route: escalate
  judge_eligible: true
"""


def test_first_match_wins() -> None:
    table = small_table(ADVANCE_ON_PASS + ESCALATE_CONCERNS)
    match = evaluate(table, make_inputs(verdict="pass"))
    assert (match.rule.id, match.route) == ("advance-pass", Route.ADVANCE)


def test_an_unnamed_input_is_unconstrained() -> None:
    table = small_table(ADVANCE_ON_PASS)
    for standing in ("stated", "derived", "none"):
        match = evaluate(table, make_inputs(verdict="pass", standing=standing))
        assert match.rule.id == "advance-pass"


def test_unknown_matches_only_named_unknown() -> None:
    named = """\
- id: unknown-review
  when: {outcome: completed, verdict: unknown}
  route: escalate
  judge_eligible: true
"""
    table = small_table(ADVANCE_ON_PASS + named)
    assert evaluate(table, make_inputs(verdict="unknown")).rule.id == "unknown-review"
    # Without a rule naming unknown, it reaches the catch-all, not "any value".
    plain = small_table(ADVANCE_ON_PASS + ESCALATE_CONCERNS)
    assert evaluate(plain, make_inputs(verdict="unknown")).rule.id == "catch-all"


def test_advance_is_passed_over_on_a_blocked_node() -> None:
    table = small_table(ADVANCE_ON_PASS)
    match = evaluate(table, make_inputs(verdict="pass", node_state="blocked"))
    assert match.rule.id == "catch-all"


def test_advance_is_passed_over_on_a_done_node() -> None:
    table = small_table(ADVANCE_ON_PASS)
    assert evaluate(table, make_inputs(verdict="pass", node_state="done")).route is (
        Route.ESCALATE
    )


def test_rerun_limit_falls_through_to_next_rule() -> None:
    table = small_table(RERUN_ON_CONCERNS + ESCALATE_CONCERNS)
    first = evaluate(table, make_inputs(attempt=1, verdict="concerns"))
    second = evaluate(table, make_inputs(attempt=2, verdict="concerns"))
    assert (first.rule.id, first.route) == ("rerun-concerns", Route.RERUN)
    assert (second.rule.id, second.route) == ("escalate-concerns", Route.ESCALATE)


def test_rerun_parameters_are_recorded() -> None:
    table = small_table(RERUN_ON_CONCERNS)
    match = evaluate(table, make_inputs(attempt=1, verdict="concerns"))
    assert match.parameters == {"max_attempts": 2}


def test_a_rerun_rule_not_naming_step_is_passed_over_when_step_is_unknown() -> None:
    unnamed = """\
- id: rerun-any-step
  when: {outcome: completed, verdict: concerns}
  route: rerun
  max_attempts: 5
"""
    table = small_table(unnamed + ESCALATE_CONCERNS)
    unknown_step = make_inputs(attempt=None, verdict="concerns", step="unknown")
    assert evaluate(table, unknown_step).rule.id == "escalate-concerns"
    known_step = make_inputs(attempt=1, verdict="concerns")
    assert evaluate(table, known_step).rule.id == "rerun-any-step"


def test_a_rerun_without_a_counted_attempt_is_not_eligible() -> None:
    table = small_table(RERUN_ON_CONCERNS)
    inputs = make_inputs(attempt=None, verdict="concerns")
    assert evaluate(table, inputs).route is Route.ESCALATE


def test_rerun_is_passed_over_on_a_blocked_node() -> None:
    table = small_table(RERUN_ON_CONCERNS)
    inputs = make_inputs(verdict="concerns", node_state="blocked")
    assert evaluate(table, inputs).rule.id == "catch-all"


def test_the_catch_all_always_applies() -> None:
    table = small_table()
    for outcome in ("completed", "paused", "failed", "orphaned", "unknown"):
        assert evaluate(table, make_inputs(outcome=outcome)).rule.id == "catch-all"
