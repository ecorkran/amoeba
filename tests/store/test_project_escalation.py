"""D4: project-scoped escalations, deduplicated on project and fault kind."""

from __future__ import annotations

from pathlib import Path

import pytest
from feed_harness import post_intent, raw_changes

from amoeba.store import (
    BlockedKind,
    ChangeKind,
    Channel,
    InvalidTransitionError,
    Message,
    NodeKind,
    Store,
)

PROJECT = "demo"
KIND = "plan_read_failed"
PAYLOAD = {"error": "boom"}


def _raise(store: Store, kind: str = KIND, project: str = PROJECT) -> Message:
    return store.raise_project_escalation(project, fault_kind=kind, payload=PAYLOAD)


def test_raising_twice_returns_the_same_row(store: Store) -> None:
    first = _raise(store)
    second = _raise(store)

    assert first.id == second.id
    assert first.fault_kind == KIND and first.payload == PAYLOAD
    assert first.node_id is None and first.blocked_state_id is None
    assert first.channel is Channel.ESCALATION and first.closed_at is None
    assert len(store.messages(PROJECT, channel=Channel.ESCALATION)) == 1


def test_a_second_kind_and_a_second_project_get_their_own_rows(store: Store) -> None:
    base = _raise(store)

    assert _raise(store, "other_kind").id != base.id
    assert _raise(store, project="elsewhere").id != base.id
    assert len(store.open_project_escalations(PROJECT)) == 2


def test_after_close_raising_opens_a_new_row(store: Store) -> None:
    first = _raise(store)
    closed = store.close_project_escalation(first.id, closed_by="runner")
    again = _raise(store)

    assert closed.closed_at is not None and closed.closed_by == "runner"
    assert again.id != first.id
    assert [m.id for m in store.open_project_escalations(PROJECT)] == [again.id]


def test_open_rows_are_in_seq_order_and_exclude_closed_and_node_rows(
    store: Store,
) -> None:
    node = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")
    store.block(node.id, kind=BlockedKind.HUMAN, context="c")
    first = _raise(store, "a")
    closed = _raise(store, "b")
    third = _raise(store, "c")
    store.close_project_escalation(closed.id, closed_by="runner")

    opened = store.open_project_escalations(PROJECT)

    assert [m.id for m in opened] == [first.id, third.id]
    assert [m.seq for m in opened] == sorted(m.seq for m in opened)


def test_close_refuses_a_missing_node_intent_or_closed_row(store: Store) -> None:
    node = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")
    store.block(node.id, kind=BlockedKind.HUMAN, context="c")
    [node_escalation] = store.messages(PROJECT, channel=Channel.ESCALATION)
    closed = _raise(store)
    store.close_project_escalation(closed.id, closed_by="runner")

    for message_id in ("no-such-id", node_escalation.id, closed.id):
        with pytest.raises(InvalidTransitionError):
            store.close_project_escalation(message_id, closed_by="runner")

    unchanged = store.messages(PROJECT, channel=Channel.ESCALATION)[0]
    assert unchanged.id == node_escalation.id and unchanged.closed_at is None


def test_an_intent_row_cannot_be_closed(store: Store) -> None:
    node = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")
    post_intent(store, "s-1", node.id, PROJECT)
    [intent] = store.pending_intents(PROJECT)

    with pytest.raises(InvalidTransitionError):
        store.close_project_escalation(intent.id, closed_by="runner")


@pytest.mark.parametrize("kind", ["", "   "])
def test_an_empty_fault_kind_raises_and_writes_nothing(store: Store, kind: str) -> None:
    with pytest.raises(ValueError, match="fault_kind"):
        _raise(store, kind)
    assert store.messages(PROJECT, channel=Channel.ESCALATION) == []


def test_an_unserializable_payload_raises_and_writes_nothing(store: Store) -> None:
    with pytest.raises(ValueError, match="payload"):
        store.raise_project_escalation(
            PROJECT, fault_kind=KIND, payload={"x": object()}
        )
    assert store.messages(PROJECT, channel=Channel.ESCALATION) == []


def test_an_empty_closed_by_raises_and_changes_nothing(store: Store) -> None:
    row = _raise(store)
    with pytest.raises(ValueError, match="closed_by"):
        store.close_project_escalation(row.id, closed_by="")
    assert [m.id for m in store.open_project_escalations(PROJECT)] == [row.id]


def test_the_raise_is_on_the_feed_and_the_close_is_not(store: Store) -> None:
    row = _raise(store)
    posted = [
        c for c in raw_changes(store, PROJECT) if c.kind is ChangeKind.MESSAGE_POSTED
    ]
    assert len(posted) == 1
    assert posted[0].payload == {"channel": Channel.ESCALATION.value}

    before = len(raw_changes(store, PROJECT))
    store.close_project_escalation(row.id, closed_by="runner")
    assert len(raw_changes(store, PROJECT)) == before


def test_a_node_escalation_is_unchanged(store: Store) -> None:
    node = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")
    blocked = store.block(node.id, kind=BlockedKind.HUMAN, context="c")
    _raise(store)

    node_rows = [
        m
        for m in store.messages(PROJECT, channel=Channel.ESCALATION)
        if m.node_id is not None
    ]
    assert [m.blocked_state_id for m in node_rows] == [blocked.id]
    assert node_rows[0].fault_kind is None and node_rows[0].closed_at is None
    assert store.pending_intents(PROJECT) == []


def test_reads_work_through_a_read_only_handle(store_file: Path) -> None:
    with Store.open(store_file) as store:
        row = _raise(store)
    with Store.open_read_only(store_file) as reader:
        assert [m.id for m in reader.open_project_escalations(PROJECT)] == [row.id]
