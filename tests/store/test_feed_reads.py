"""The ``changes`` read: ordering, cursor, scoping, and limit."""

from __future__ import annotations

import pytest

from amoeba.store import ChangeKind, NodeKind, NodeStatus, Store

PROJECT = "demo"
OTHER = "other"


def _node(store: Store, project_id: str = PROJECT) -> str:
    return store.create_node(project_id=project_id, kind=NodeKind.SLICE, title="n").id


def test_an_empty_project_has_no_changes(store: Store) -> None:
    assert store.changes(PROJECT, limit=10) == []


def test_after_returns_only_later_changes_in_order(store: Store) -> None:
    for _ in range(4):
        _node(store)
    every = store.changes(PROJECT, limit=10)
    later = store.changes(PROJECT, after=every[1].seq, limit=10)
    assert later == every[2:]


def test_limit_caps_the_result(store: Store) -> None:
    for _ in range(5):
        _node(store)
    assert len(store.changes(PROJECT, limit=2)) == 2


@pytest.mark.parametrize("limit", [0, -1])
def test_a_limit_below_one_raises(store: Store, limit: int) -> None:
    with pytest.raises(ValueError, match="limit"):
        store.changes(PROJECT, limit=limit)


def test_two_projects_feeds_are_independent(store: Store) -> None:
    mine = _node(store)
    theirs = _node(store, OTHER)
    assert [c.node_id for c in store.changes(PROJECT, limit=10)] == [mine]
    assert [c.node_id for c in store.changes(OTHER, limit=10)] == [theirs]


def test_seq_has_no_gaps_after_mixed_writes(store: Store) -> None:
    node_id = _node(store)
    store.update_node_status(node_id, NodeStatus.IN_PROGRESS)
    store.update_node_status(node_id, NodeStatus.IN_PROGRESS)
    store.update_node_status(node_id, NodeStatus.DONE)
    seqs = [change.seq for change in store.changes(PROJECT, limit=10)]
    assert seqs == [1, 2, 3]


def test_the_payload_is_a_decoded_mapping(store: Store) -> None:
    node_id = _node(store)
    store.update_node_status(node_id, NodeStatus.DONE)
    change = store.changes(PROJECT, limit=10)[-1]
    assert change.kind is ChangeKind.NODE_STATUS_CHANGED
    assert change.payload["to"] == NodeStatus.DONE.value
