"""D8: a routing decision clears its entry's routing flag, in its own transaction."""

from __future__ import annotations

import pytest
from fault_injection import InjectedFailureError, fail_on_statement
from routing_helpers import PROJECT, TABLE, decision_input, issue_entry, make_node

from amoeba.store import NodeStatus, StatusEffect, Store, sql


def _unrouted_ids(store: Store) -> list[str]:
    return [entry.id for entry in store.unrouted_outcomes(PROJECT)]


def test_a_decision_clears_the_flag_on_its_entry_only(store: Store) -> None:
    node_id = make_node(store)
    routed = issue_entry(store, node_id)
    waiting = issue_entry(store, node_id)
    assert _unrouted_ids(store) == [routed, waiting]

    store.record_routing_decision(
        decision_input(node_id, routed),
        table=TABLE,
        effect=None,
        attempt_step=None,
    )

    assert _unrouted_ids(store) == [waiting]
    cleared = store.journal_entry(routed)
    assert cleared is not None and cleared.awaits_routing is False


def test_a_decision_without_an_entry_clears_nothing(store: Store) -> None:
    node_id = make_node(store)
    waiting = issue_entry(store, node_id)

    store.record_routing_decision(
        decision_input(node_id), table=TABLE, effect=None, attempt_step=None
    )

    assert _unrouted_ids(store) == [waiting]


def test_a_decision_that_fails_validation_leaves_the_flag_set(store: Store) -> None:
    node_id = make_node(store)
    entry_id = issue_entry(store, node_id)

    with pytest.raises(ValueError, match="rule_id"):
        store.record_routing_decision(
            decision_input(node_id, entry_id, rule_id=""),
            table=TABLE,
            effect=None,
            attempt_step=None,
        )

    assert _unrouted_ids(store) == [entry_id]


def test_a_failure_after_the_clear_restores_the_flag(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    node_id = make_node(store)
    entry_id = issue_entry(store, node_id)
    fail_on_statement(monkeypatch, store, sql.UPDATE_NODE_STATUS)

    with pytest.raises(InjectedFailureError):
        store.record_routing_decision(
            decision_input(node_id, entry_id),
            table=TABLE,
            effect=StatusEffect(NodeStatus.DONE),
            attempt_step=None,
        )

    monkeypatch.undo()
    assert _unrouted_ids(store) == [entry_id]
    assert store.routing_decision_for_entry(entry_id) is None
