"""D5: an injected failure at any step of a routing decision leaves none of it."""

from __future__ import annotations

from typing import Any

import pytest
from fault_injection import InjectedFailureError, fail_on_statement
from routing_helpers import PROJECT, TABLE, decision_input, issue_entry, make_node

from amoeba.store import (
    BlockEffect,
    Channel,
    InvalidTransitionError,
    NodeStatus,
    RoutingDecisionInput,
    StatusEffect,
    Store,
    sql,
    sql_inbox,
    sql_runner,
)

_STATUS_STEPS = {
    "table version": sql_runner.INSERT_TABLE_VERSION,
    "decision": sql_runner.INSERT_DECISION,
    "attempt count": sql_runner.UPSERT_ATTEMPT_COUNT,
    "status effect": sql.UPDATE_NODE_STATUS,
}


def _assert_nothing_landed(store: Store, decision: RoutingDecisionInput) -> None:
    assert store.routing_table_version(TABLE.version) is None
    assert store.routing_decisions(decision.node_id) == []
    assert store.attempt_count(decision.node_id, "P5") == 0
    node = store.get_node(decision.node_id)
    assert node is not None and node.status is NodeStatus.RUNNABLE
    assert store.blocked_state_for(decision.node_id, include_resolved=True) is None
    assert store.messages(PROJECT, channel=Channel.ESCALATION) == []


@pytest.mark.parametrize("step", list(_STATUS_STEPS))
def test_a_failure_at_each_step_of_a_status_decision_leaves_nothing(
    store: Store, monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    node_id = make_node(store)
    decision = decision_input(node_id, issue_entry(store, node_id))
    fail_on_statement(monkeypatch, store, _STATUS_STEPS[step])

    with pytest.raises(InjectedFailureError):
        store.record_routing_decision(
            decision,
            table=TABLE,
            effect=StatusEffect(NodeStatus.DONE),
            attempt_step="P5",
        )

    monkeypatch.undo()
    _assert_nothing_landed(store, decision)


@pytest.mark.parametrize(
    "statement", [sql_inbox.INSERT_MESSAGE, sql.INSERT_BLOCKED_STATE]
)
def test_a_failure_in_a_block_effect_leaves_nothing(
    store: Store, monkeypatch: pytest.MonkeyPatch, statement: str
) -> None:
    node_id = make_node(store)
    decision = decision_input(node_id)
    fail_on_statement(monkeypatch, store, statement)

    with pytest.raises(InjectedFailureError):
        store.record_routing_decision(
            decision, table=TABLE, effect=BlockEffect("stop"), attempt_step="P5"
        )

    monkeypatch.undo()
    _assert_nothing_landed(store, decision)


@pytest.mark.parametrize(
    "changes",
    [
        {"rule_id": ""},
        {"inputs": {"x": object()}},
        {"table_version": "v2"},
        {"journal_entry_id": "no-such-entry"},
    ],
)
def test_a_validation_failure_through_the_public_method_writes_nothing(
    store: Store, changes: dict[str, Any]
) -> None:
    node_id = make_node(store)
    decision = decision_input(node_id, **changes)

    with pytest.raises((ValueError, InvalidTransitionError)):
        store.record_routing_decision(
            decision, table=TABLE, effect=None, attempt_step="P5"
        )

    _assert_nothing_landed(store, decision)
