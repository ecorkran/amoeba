"""Emission triggers: every write to a tracked table emits its change, once."""

from __future__ import annotations

import sqlite3

from feed_harness import raw_changes

from amoeba.store import BlockedKind, CFReference, NodeKind, NodeStatus, Store, sql
from amoeba.store.feed_models import ChangeKind

PROJECT = "demo"


def _node(store: Store, status: NodeStatus = NodeStatus.RUNNABLE) -> str:
    return store.create_node(
        project_id=PROJECT, kind=NodeKind.SLICE, title="n", status=status
    ).id


def _of_kind(store: Store, kind: ChangeKind) -> list[dict[str, object]]:
    return [dict(c.payload) for c in raw_changes(store, PROJECT) if c.kind is kind]


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------


def test_create_node_emits_one_node_created_with_the_initial_status(
    store: Store,
) -> None:
    parent = _node(store)
    child = store.create_node(
        project_id=PROJECT,
        kind=NodeKind.GATE,
        title="c",
        parent_id=parent,
        status=NodeStatus.IN_PROGRESS,
    )

    changes = raw_changes(store, PROJECT)
    assert [c.kind for c in changes] == [ChangeKind.NODE_CREATED] * 2
    last = changes[-1]
    assert (last.node_id, last.subject_id) == (child.id, child.id)
    assert last.payload == {
        "kind": NodeKind.GATE.value,
        "parent_id": parent,
        "status": NodeStatus.IN_PROGRESS.value,
    }
    assert last.recorded_at == child.created_at


def test_a_status_update_emits_from_and_to(store: Store) -> None:
    node_id = _node(store)
    updated = store.update_node_status(node_id, NodeStatus.DONE)

    changes = raw_changes(store, PROJECT)
    assert changes[-1].kind is ChangeKind.NODE_STATUS_CHANGED
    assert changes[-1].payload == {
        "from": NodeStatus.RUNNABLE.value,
        "to": NodeStatus.DONE.value,
    }
    assert changes[-1].recorded_at == updated.updated_at


def test_an_update_to_the_same_status_emits_nothing(store: Store) -> None:
    node_id = _node(store)
    store.update_node_status(node_id, NodeStatus.RUNNABLE)
    assert _of_kind(store, ChangeKind.NODE_STATUS_CHANGED) == []


def test_block_and_resolve_each_emit_their_transition(store: Store) -> None:
    node_id = _node(store)
    store.block(node_id, kind=BlockedKind.HUMAN, context="decide")
    store.resolve(node_id, resolved_by="pm", detail="go")

    assert _of_kind(store, ChangeKind.NODE_STATUS_CHANGED) == [
        {"from": NodeStatus.RUNNABLE.value, "to": NodeStatus.BLOCKED_ON_HUMAN.value},
        {"from": NodeStatus.BLOCKED_ON_HUMAN.value, "to": NodeStatus.RUNNABLE.value},
    ]


def test_other_node_updates_emit_nothing(store: Store) -> None:
    node_id = _node(store)
    store.update_cf_reference(node_id, CFReference(slice_name="renamed"))
    assert _of_kind(store, ChangeKind.NODE_STATUS_CHANGED) == []


def test_a_rolled_back_write_leaves_no_change(store: Store) -> None:
    with sqlite3.connect(store.path) as connection:
        connection.execute("BEGIN")
        connection.execute(
            sql.INSERT_NODE,
            ("n-x", PROJECT, None, "slice", "runnable", "x")
            + (None,) * 7
            + ("2026-10-15T00:00:00+00:00",) * 2,
        )
        connection.rollback()
    assert raw_changes(store, PROJECT) == []
