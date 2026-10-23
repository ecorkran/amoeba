"""Escalating an unexpected fault: node block or project-scoped row."""

from __future__ import annotations

import pytest

from amoeba.runner.faults import FaultKind, NodeContext, escalate
from amoeba.store import (
    BlockedKind,
    CommandKind,
    Node,
    NodeKind,
    NodeStatus,
    Store,
)

PROJECT = "demo"
ERROR = RuntimeError("planner exploded")


@pytest.fixture
def node(store: Store) -> Node:
    return store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")


def _in(node_id: str | None) -> NodeContext:
    context = NodeContext()
    if node_id is not None:
        context.set(node_id)
    return context


def _escalate(store: Store, context: NodeContext) -> None:
    escalate(store, PROJECT, context, FaultKind.UNEXPECTED_FAULT, ERROR)


def test_a_free_node_is_blocked_on_a_human_with_the_fault_named(
    store: Store, node: Node
) -> None:
    _escalate(store, _in(node.id))

    blocked = store.blocked_state_for(node.id)
    assert blocked is not None and blocked.kind is BlockedKind.HUMAN
    assert (
        "unexpected_fault" in blocked.context and "planner exploded" in blocked.context
    )
    assert store.open_project_escalations(PROJECT) == []


def test_an_already_blocked_node_gets_nothing_more(store: Store, node: Node) -> None:
    store.block(node.id, kind=BlockedKind.HUMAN, context="earlier")
    before = len(list(store.all_blocked_states(node.id)))

    _escalate(store, _in(node.id))
    _escalate(store, _in(node.id))

    assert len(list(store.all_blocked_states(node.id))) == before
    assert store.open_project_escalations(PROJECT) == []


def test_a_node_with_a_run_in_flight_takes_the_project_path(
    store: Store, node: Node
) -> None:
    entry = store.journal_issue(
        node.id,
        kind=CommandKind.SQ_RUN,
        parameters={"pipeline": "p", "params": {}, "run_id": "run-1"},
    )

    _escalate(store, _in(node.id))

    assert store.blocked_state_for(node.id) is None
    [row] = store.open_project_escalations(PROJECT)
    assert row.fault_kind == "unexpected_fault"
    assert row.payload is not None
    assert row.payload["node_id"] == node.id
    assert row.payload["run_ids"] == ["run-1"]
    assert entry.id  # the entry stays unresolved


def test_a_done_node_takes_the_project_path(store: Store, node: Node) -> None:
    store.update_node_status(node.id, NodeStatus.DONE)

    _escalate(store, _in(node.id))

    assert store.blocked_state_for(node.id) is None
    [row] = store.open_project_escalations(PROJECT)
    assert row.payload is not None and row.payload["node_id"] == node.id


def test_no_node_in_context_takes_the_project_path(store: Store) -> None:
    _escalate(store, _in(None))

    [row] = store.open_project_escalations(PROJECT)
    assert row.payload is not None and row.payload["node_id"] is None


def test_a_repeated_fault_adds_no_rows(store: Store) -> None:
    _escalate(store, _in(None))
    _escalate(store, _in(None))

    assert len(store.open_project_escalations(PROJECT)) == 1
