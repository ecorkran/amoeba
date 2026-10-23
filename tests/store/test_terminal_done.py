"""D1: ``done`` is terminal on every store write path."""

from __future__ import annotations

import pytest

from amoeba.store import (
    REQUIRED_PARAMETER_KEYS,
    BlockedKind,
    Channel,
    CommandKind,
    InvalidTransitionError,
    NodeKind,
    NodeStatus,
    Store,
    sql,
)

PROJECT = "demo"
STAGED_AT = "2026-10-22T00:00:00+00:00"


def _done_node(store: Store) -> str:
    return store.create_node(
        project_id=PROJECT, kind=NodeKind.SLICE, title="x", status=NodeStatus.DONE
    ).id


def _parameters(kind: CommandKind) -> dict[str, object]:
    return dict.fromkeys(REQUIRED_PARAMETER_KEYS[kind], "value")


def _issue(store: Store, node_id: str) -> str:
    return store.journal_issue(
        node_id, kind=CommandKind.SQ_RUN, parameters=_parameters(CommandKind.SQ_RUN)
    ).id


def _force_status(store: Store, node_id: str, status: NodeStatus) -> None:
    """Write a status with raw SQL, as a store from before 009 could hold."""
    with store._connection:  # pyright: ignore[reportPrivateUsage]
        store._connection.execute(  # pyright: ignore[reportPrivateUsage]
            sql.UPDATE_NODE_STATUS, (status.value, STAGED_AT, node_id)
        )


# --------------------------------------------------------------------------
# Task 3.1: block() and journal_escalate on a done node
# --------------------------------------------------------------------------


@pytest.mark.parametrize("kind", list(BlockedKind))
def test_block_of_a_done_node_raises_and_changes_nothing(
    store: Store, kind: BlockedKind
) -> None:
    node_id = _done_node(store)

    with pytest.raises(InvalidTransitionError, match=node_id):
        store.block(node_id, kind=kind, context="stop")

    node = store.get_node(node_id)
    assert node is not None and node.status is NodeStatus.DONE
    assert store.blocked_state_for(node_id, include_resolved=True) is None
    assert store.messages(PROJECT, channel=Channel.ESCALATION) == []


def test_journal_escalate_on_a_done_node_raises_and_changes_nothing(
    store: Store,
) -> None:
    node_id = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="x").id
    entry_id = _issue(store, node_id)
    _force_status(store, node_id, NodeStatus.DONE)

    with pytest.raises(InvalidTransitionError, match=node_id):
        store.journal_escalate(entry_id, reason="unknown outcome")

    node = store.get_node(node_id)
    assert node is not None and node.status is NodeStatus.DONE
    entry = store.journal_entry(entry_id)
    assert entry is not None and not entry.is_resolved
    assert store.blocked_state_for(node_id, include_resolved=True) is None
    assert store.messages(PROJECT, channel=Channel.ESCALATION) == []
