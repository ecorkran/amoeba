"""The route stage, on a real store with ingested-shape entries (D5)."""

from __future__ import annotations

from typing import Any

from amoeba.process import RunOutcome
from amoeba.runner.faults import NodeContext
from amoeba.runner.ingest.record import OUTCOME_VANISHED
from amoeba.runner.routing.stage import route_outcomes
from amoeba.store import (
    BlockedKind,
    NodeStatus,
    ReviewVerdict,
    Route,
    RoutingDecision,
    Store,
)
from runner.routing.entry_support import (
    PROJECT,
    StagedReview,
    concern,
    stage_node,
    stage_outcome,
)
from runner.routing.table_support import TEST_AMOEBA_VERSION, shipped_table

TABLE = shipped_table()
STEP = "slice_design"


def _route(store: Store, context: NodeContext | None = None) -> bool:
    return route_outcomes(
        store, PROJECT, TABLE, TEST_AMOEBA_VERSION, context or NodeContext()
    )


def _only_decision(store: Store, node_id: str) -> RoutingDecision:
    [decision] = store.routing_decisions(node_id)
    return decision


def _open_blocks(store: Store, node_id: str) -> list[BlockedKind]:
    return [s.kind for s in store.all_blocked_states(node_id) if not s.is_resolved]


def _status(store: Store, node_id: str) -> NodeStatus:
    node = store.get_node(node_id)
    assert node is not None
    return node.status


def _passed() -> tuple[StagedReview, ...]:
    return (StagedReview("v-pass", verdict=ReviewVerdict.PASS),)


def _concerned(verdict_id: str, summary: str) -> tuple[StagedReview, ...]:
    return (StagedReview(verdict_id, findings=(concern(summary),)),)


def test_a_stated_pass_marks_the_step_done_and_counts_attempt_one(
    store: Store,
) -> None:
    node_id = stage_node(store)
    stage_outcome(store, node_id, reviews=_passed())

    assert _route(store) is True

    decision = _only_decision(store, node_id)
    assert decision.rule_id == "advance-on-stated-pass"
    assert decision.route is Route.ADVANCE
    assert decision.attempt_step == STEP and decision.attempt_count == 1
    assert _status(store, node_id) is NodeStatus.DONE
    assert store.unrouted_outcomes(PROJECT) == []


def test_new_concerns_rerun_then_escalate_on_the_second_outcome(
    store: Store,
) -> None:
    node_id = stage_node(store)
    stage_outcome(
        store, node_id, run_id="run-1", reviews=_concerned("v-1", "first problem")
    )
    _route(store)

    first = _only_decision(store, node_id)
    assert (first.rule_id, first.route) == ("rerun-new-concerns", Route.RERUN)
    assert first.route_parameters == {"max_attempts": 2}
    assert _status(store, node_id) is NodeStatus.RUNNABLE
    assert _open_blocks(store, node_id) == []

    stage_outcome(
        store, node_id, run_id="run-2", reviews=_concerned("v-2", "another problem")
    )
    _route(store)

    second = store.routing_decisions(node_id)[-1]
    assert (second.rule_id, second.route) == (
        "escalate-completed-concerns",
        Route.ESCALATE,
    )
    assert second.attempt_count == 2
    assert second.route_parameters == {"judge_eligible": True}
    assert _open_blocks(store, node_id) == [BlockedKind.HUMAN]


def test_a_recurring_concern_is_not_rerun(store: Store) -> None:
    node_id = stage_node(store)
    stage_outcome(
        store, node_id, run_id="run-1", reviews=_concerned("v-1", "same problem")
    )
    _route(store)
    stage_outcome(
        store, node_id, run_id="run-2", reviews=_concerned("v-2", "same problem")
    )
    _route(store)

    assert store.routing_decisions(node_id)[-1].rule_id == "escalate-completed-concerns"


def test_a_paused_entry_escalates_with_no_second_block(store: Store) -> None:
    node_id = stage_node(store)
    document = {
        "run_id": "run-20261025-p4-aaaa0001",
        "outcome": "paused",
        "checkpoint": {"kind": "awaits_human", "is_loop": False},
    }
    stage_outcome(
        store,
        node_id,
        outcome=RunOutcome.PAUSED.value,
        document=document,
        block=BlockedKind.SQ_CHECKPOINT,
    )

    _route(store)

    decision = _only_decision(store, node_id)
    assert (decision.rule_id, decision.route) == (
        "escalate-everything-else",
        Route.ESCALATE,
    )
    assert _status(store, node_id) is NodeStatus.BLOCKED_ON_SQ_CHECKPOINT
    assert _open_blocks(store, node_id) == [BlockedKind.SQ_CHECKPOINT]


def test_failed_orphaned_vanished_and_launch_failed_escalate_without_a_second_block(
    store: Store,
) -> None:
    cases: list[dict[str, Any]] = [
        {"outcome": RunOutcome.FAILED.value},
        {"outcome": RunOutcome.ORPHANED.value},
        {"outcome": OUTCOME_VANISHED},
        {"launch_failure": "sq_missing"},
    ]
    nodes: list[str] = []
    for position, case in enumerate(cases):
        node_id = stage_node(store)
        nodes.append(node_id)
        stage_outcome(
            store, node_id, run_id=f"run-{position}", block=BlockedKind.HUMAN, **case
        )

    _route(store)

    for node_id in nodes:
        decision = _only_decision(store, node_id)
        assert decision.route is Route.ESCALATE
        assert _open_blocks(store, node_id) == [BlockedKind.HUMAN]
    assert store.unrouted_outcomes(PROJECT) == []


def test_an_entry_with_a_missing_verdict_id_escalates(store: Store) -> None:
    node_id = stage_node(store)
    stage_outcome(store, node_id, verdict_ids=["never-recorded"])

    _route(store)

    decision = _only_decision(store, node_id)
    assert decision.rule_id == "escalate-everything-else"
    assert decision.inputs["verdict"] == "unknown"
    assert _open_blocks(store, node_id) == [BlockedKind.HUMAN]


def test_a_review_fault_escalates_with_unknown_review_inputs(store: Store) -> None:
    node_id = stage_node(store)
    stage_outcome(store, node_id, review_fault="could not read the file")

    _route(store)

    decision = _only_decision(store, node_id)
    assert decision.inputs["verdict"] == decision.inputs["standing"] == "unknown"
    assert decision.route is Route.ESCALATE


def test_an_unknown_step_is_routed_without_counting_an_attempt(store: Store) -> None:
    node_id = stage_node(store, "a_phase_cf_invented")
    stage_outcome(store, node_id, reviews=_passed())

    _route(store)

    decision = _only_decision(store, node_id)
    assert decision.inputs["step"] == "unknown"
    assert decision.inputs["attempt"] is None
    assert decision.attempt_step is None and decision.attempt_count is None
    # The shipped advance rule does not name step, and advance has no attempt limit.
    assert decision.route is Route.ADVANCE


def test_the_decision_records_the_table_and_versions(store: Store) -> None:
    node_id = stage_node(store)
    entry = stage_outcome(store, node_id, reviews=_passed())

    _route(store)

    decision = _only_decision(store, node_id)
    assert decision.journal_entry_id == entry.id
    assert decision.table_version == TABLE.version
    assert decision.amoeba_version == TEST_AMOEBA_VERSION
    stored = store.routing_table_version(TABLE.version)
    assert stored is not None and stored.content == TABLE.content


def test_the_table_version_is_stored_once_across_several_decisions(
    store: Store,
) -> None:
    nodes = [stage_node(store) for _ in range(3)]
    for position, node_id in enumerate(nodes):
        stage_outcome(
            store,
            node_id,
            run_id=f"run-{position}",
            reviews=(StagedReview(f"v-{position}", verdict=ReviewVerdict.PASS),),
        )

    _route(store)

    decisions = [_only_decision(store, node_id) for node_id in nodes]
    assert {d.table_version for d in decisions} == {TABLE.version}
    assert store.unrouted_outcomes(PROJECT) == []


def test_nothing_to_route_writes_nothing(store: Store) -> None:
    assert _route(store) is False


def test_a_routed_entry_is_not_routed_again(store: Store) -> None:
    node_id = stage_node(store)
    stage_outcome(store, node_id, reviews=_passed())
    _route(store)

    assert _route(store) is False
    assert len(store.routing_decisions(node_id)) == 1


def test_the_context_names_the_node_being_routed(store: Store) -> None:
    node_id = stage_node(store)
    stage_outcome(store, node_id, reviews=_passed())
    context = NodeContext()

    _route(store, context)

    assert context.node_id == node_id
