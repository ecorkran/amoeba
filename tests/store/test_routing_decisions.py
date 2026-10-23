"""D5-D7: a routing decision, its table version, its count and its effect."""

from __future__ import annotations

import pytest
from routing_helpers import PROJECT, TABLE, decision_input, issue_entry, make_node

from amoeba.store import (
    BlockedKind,
    BlockEffect,
    Channel,
    InvalidTransitionError,
    NodeStatus,
    RoutingTableVersion,
    StatusEffect,
    Store,
    StoreIntegrityError,
)


def _status(store: Store, node_id: str) -> NodeStatus:
    node = store.get_node(node_id)
    assert node is not None
    return node.status


def _nothing_recorded(store: Store, node_id: str) -> None:
    assert store.routing_decisions(node_id) == []
    assert store.routing_table_version(TABLE.version) is None
    assert store.attempt_count(node_id, "P5") == 0


def test_happy_path_records_version_decision_count_and_status(store: Store) -> None:
    node_id = make_node(store)
    entry_id = issue_entry(store, node_id)

    stored = store.record_routing_decision(
        decision_input(node_id, entry_id),
        table=TABLE,
        effect=StatusEffect(NodeStatus.DONE),
        attempt_step="P5",
    )

    assert stored.attempt_step == "P5" and stored.attempt_count == 1
    assert stored.inputs == {"outcome": "completed"}
    assert store.routing_decision_for_entry(entry_id) == stored
    version = store.routing_table_version("v1")
    assert version is not None and version.content == TABLE.content
    assert store.attempt_count(node_id, "P5") == 1
    assert _status(store, node_id) is NodeStatus.DONE


def test_the_same_version_is_stored_once_and_changed_content_is_refused(
    store: Store,
) -> None:
    node_id = make_node(store)
    store.record_routing_decision(
        decision_input(node_id), table=TABLE, effect=None, attempt_step=None
    )
    store.record_routing_decision(
        decision_input(node_id), table=TABLE, effect=None, attempt_step=None
    )
    assert len(store.routing_decisions(node_id)) == 2

    with pytest.raises(StoreIntegrityError):
        store.record_routing_decision(
            decision_input(node_id),
            table=RoutingTableVersion("v1", "edited"),
            effect=None,
            attempt_step=None,
        )

    assert len(store.routing_decisions(node_id)) == 2
    version = store.routing_table_version("v1")
    assert version is not None and version.content == TABLE.content


def test_counts_rise_per_node_and_step(store: Store) -> None:
    node_id = make_node(store)
    first, second = issue_entry(store, node_id), issue_entry(store, node_id)
    assert store.attempt_count(node_id, "P5") == 0

    one = store.record_routing_decision(
        decision_input(node_id, first), table=TABLE, effect=None, attempt_step="P5"
    )
    two = store.record_routing_decision(
        decision_input(node_id, second), table=TABLE, effect=None, attempt_step="P5"
    )
    other = store.record_routing_decision(
        decision_input(node_id), table=TABLE, effect=None, attempt_step="P6"
    )
    uncounted = store.record_routing_decision(
        decision_input(node_id), table=TABLE, effect=None, attempt_step=None
    )

    assert (one.attempt_count, two.attempt_count, other.attempt_count) == (1, 2, 1)
    assert uncounted.attempt_count is None and uncounted.attempt_step is None
    assert store.attempt_count(node_id, "P5") == 2
    assert store.attempt_count(node_id, "P6") == 1


def test_a_second_decision_for_one_entry_is_refused(store: Store) -> None:
    node_id = make_node(store)
    entry_id = issue_entry(store, node_id)
    store.record_routing_decision(
        decision_input(node_id, entry_id), table=TABLE, effect=None, attempt_step="P5"
    )

    with pytest.raises(StoreIntegrityError):
        store.record_routing_decision(
            decision_input(node_id, entry_id),
            table=TABLE,
            effect=None,
            attempt_step="P5",
        )

    assert len(store.routing_decisions(node_id)) == 1
    assert store.attempt_count(node_id, "P5") == 1


def test_a_block_effect_writes_a_human_block_and_its_escalation(store: Store) -> None:
    node_id = make_node(store)
    entry_id = issue_entry(store, node_id)

    store.record_routing_decision(
        decision_input(node_id, entry_id),
        table=TABLE,
        effect=BlockEffect("attempts exhausted", {"step": "P5"}),
        attempt_step=None,
    )

    blocked = store.blocked_state_for(node_id)
    assert blocked is not None and blocked.kind is BlockedKind.HUMAN
    assert blocked.context == "attempts exhausted"
    [escalation] = store.messages(PROJECT, channel=Channel.ESCALATION)
    assert escalation.blocked_state_id == blocked.id
    assert escalation.journal_entry_id == entry_id
    assert escalation.payload == {"step": "P5"}


def test_done_on_a_done_node_raises_and_records_nothing(store: Store) -> None:
    node_id = make_node(store)
    store.update_node_status(node_id, NodeStatus.DONE)

    with pytest.raises(InvalidTransitionError, match=node_id):
        store.record_routing_decision(
            decision_input(node_id),
            table=TABLE,
            effect=StatusEffect(NodeStatus.DONE),
            attempt_step="P5",
        )

    _nothing_recorded(store, node_id)


def test_done_with_an_unresolved_entry_raises_and_records_nothing(
    store: Store,
) -> None:
    node_id = make_node(store)
    entry_id = issue_entry(store, node_id, resolved=False)

    with pytest.raises(InvalidTransitionError, match=entry_id):
        store.record_routing_decision(
            decision_input(node_id, entry_id),
            table=TABLE,
            effect=StatusEffect(NodeStatus.DONE),
            attempt_step="P5",
        )

    _nothing_recorded(store, node_id)
    assert _status(store, node_id) is NodeStatus.RUNNABLE


def test_a_block_effect_on_a_blocked_node_raises_and_records_nothing(
    store: Store,
) -> None:
    node_id = make_node(store)
    store.block(node_id, kind=BlockedKind.HUMAN, context="first")

    with pytest.raises(InvalidTransitionError, match="already blocked"):
        store.record_routing_decision(
            decision_input(node_id),
            table=TABLE,
            effect=BlockEffect("second"),
            attempt_step="P5",
        )

    _nothing_recorded(store, node_id)
    assert len(store.messages(PROJECT, channel=Channel.ESCALATION)) == 1


@pytest.mark.parametrize("status", [NodeStatus.RUNNABLE, NodeStatus.BLOCKED_ON_HUMAN])
def test_a_status_effect_on_a_blocked_node_or_to_a_blocked_status_raises(
    store: Store, status: NodeStatus
) -> None:
    node_id = make_node(store)
    store.block(node_id, kind=BlockedKind.HUMAN, context="first")

    with pytest.raises(InvalidTransitionError):
        store.record_routing_decision(
            decision_input(node_id),
            table=TABLE,
            effect=StatusEffect(status),
            attempt_step="P5",
        )

    _nothing_recorded(store, node_id)
    assert _status(store, node_id) is NodeStatus.BLOCKED_ON_HUMAN


def test_a_blocked_target_status_on_a_runnable_node_raises(store: Store) -> None:
    node_id = make_node(store)

    with pytest.raises(InvalidTransitionError):
        store.record_routing_decision(
            decision_input(node_id),
            table=TABLE,
            effect=StatusEffect(NodeStatus.BLOCKED_ON_HUMAN),
            attempt_step=None,
        )

    _nothing_recorded(store, node_id)


def test_no_effect_records_the_decision_and_counter_only(store: Store) -> None:
    node_id = make_node(store)

    store.record_routing_decision(
        decision_input(node_id), table=TABLE, effect=None, attempt_step="P5"
    )

    assert _status(store, node_id) is NodeStatus.RUNNABLE
    assert store.attempt_count(node_id, "P5") == 1
    assert len(store.routing_decisions(node_id)) == 1


def test_decisions_without_an_entry_may_repeat_and_read_oldest_first(
    store: Store,
) -> None:
    node_id = make_node(store)
    ids = [
        store.record_routing_decision(
            decision_input(node_id), table=TABLE, effect=None, attempt_step=None
        ).id
        for _ in range(3)
    ]

    assert [d.id for d in store.routing_decisions(node_id)] == ids
    assert store.routing_decisions(make_node(store)) == []
