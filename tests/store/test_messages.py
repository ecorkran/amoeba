"""D3's escalation-on-block invariant and the message read API.

Intent rows are staged with the store's own ``INSERT_MESSAGE`` statement,
because the only production writer of intents is ``apply_submission``, which
this test module must not depend on.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from amoeba.store import sql_inbox
from amoeba.store.inbox_models import Channel
from amoeba.store.models import BlockedKind, InvalidTransitionError, NodeKind
from amoeba.store.store import Store

PROJECT = "demo"
STAGED_AT = "2026-09-23T00:00:00+00:00"


def _make_node(store: Store, title: str = "a slice") -> str:
    return store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title=title).id


def _escalations(store: Store, after_seq: int = 0) -> list[str]:
    """Blocked-state ids carried by escalation rows, in seq order."""
    return [
        str(message.blocked_state_id)
        for message in store.messages(
            PROJECT, channel=Channel.ESCALATION, after_seq=after_seq
        )
    ]


def _stage_intent(path: Path, message_id: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            sql_inbox.INSERT_MESSAGE,
            (
                message_id,
                PROJECT,
                Channel.INTENT.value,
                None,
                None,
                None,
                f"sub-{message_id}",
                json.dumps({"want": message_id}),
                STAGED_AT,
            ),
        )


# --------------------------------------------------------------------------
# D3: the escalation row
# --------------------------------------------------------------------------


def test_human_block_writes_exactly_one_escalation(store_file: Path) -> None:
    with Store.open(store_file) as store:
        node_id = _make_node(store)
        blocked = store.block(node_id, kind=BlockedKind.HUMAN, context="decide")

        escalations = store.messages(PROJECT, channel=Channel.ESCALATION)

    assert len(escalations) == 1
    assert escalations[0].node_id == node_id
    assert escalations[0].blocked_state_id == blocked.id
    assert escalations[0].project_id == PROJECT
    assert escalations[0].journal_entry_id is None


@pytest.mark.parametrize("kind", [BlockedKind.JUDGE, BlockedKind.SQ_CHECKPOINT])
def test_non_human_blocks_write_no_message(store_file: Path, kind: BlockedKind) -> None:
    with Store.open(store_file) as store:
        store.block(_make_node(store), kind=kind, context="machine-resolved")

        assert store.messages(PROJECT, channel=Channel.ESCALATION) == []
        assert store.messages(PROJECT, channel=Channel.INTENT) == []


def test_block_payload_round_trips_onto_the_escalation(store_file: Path) -> None:
    payload = {"options": ["ship", "hold"], "deadline": "friday"}

    with Store.open(store_file) as store:
        store.block(
            _make_node(store), kind=BlockedKind.HUMAN, context="c", payload=payload
        )
        [escalation] = store.messages(PROJECT, channel=Channel.ESCALATION)

    assert escalation.payload == payload


def test_omitted_payload_is_stored_as_null(store_file: Path) -> None:
    with Store.open(store_file) as store:
        store.block(_make_node(store), kind=BlockedKind.HUMAN, context="c")
        [escalation] = store.messages(PROJECT, channel=Channel.ESCALATION)

    assert escalation.payload is None


def test_a_failed_block_writes_no_escalation(store_file: Path) -> None:
    """The row commits with the block or neither does."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)
        store.block(node_id, kind=BlockedKind.HUMAN, context="first")

        with pytest.raises(InvalidTransitionError):
            store.block(node_id, kind=BlockedKind.HUMAN, context="second")

        assert len(store.messages(PROJECT, channel=Channel.ESCALATION)) == 1


# --------------------------------------------------------------------------
# The replay primitive
# --------------------------------------------------------------------------


def test_messages_after_seq_returns_only_later_rows_in_order(
    store_file: Path,
) -> None:
    with Store.open(store_file) as store:
        first = store.block(
            _make_node(store, "one"), kind=BlockedKind.HUMAN, context="1"
        )
        second = store.block(
            _make_node(store, "two"), kind=BlockedKind.HUMAN, context="2"
        )
        third = store.block(
            _make_node(store, "three"), kind=BlockedKind.HUMAN, context="3"
        )
        all_rows = store.messages(PROJECT, channel=Channel.ESCALATION)

    assert [row.blocked_state_id for row in all_rows] == [first.id, second.id, third.id]
    assert [row.seq for row in all_rows] == sorted(row.seq for row in all_rows)

    with Store.open_read_only(store_file) as reader:
        after_first = _escalations(reader, after_seq=all_rows[0].seq)
        again = _escalations(reader, after_seq=all_rows[0].seq)

    assert after_first == [second.id, third.id]
    assert again == after_first


def test_messages_are_scoped_to_one_channel(store_file: Path) -> None:
    with Store.open(store_file) as store:
        store.block(_make_node(store), kind=BlockedKind.HUMAN, context="c")
    _stage_intent(store_file, "i-1")

    with Store.open_read_only(store_file) as reader:
        assert [m.id for m in reader.messages(PROJECT, channel=Channel.INTENT)] == [
            "i-1"
        ]
        assert len(reader.messages(PROJECT, channel=Channel.ESCALATION)) == 1


# --------------------------------------------------------------------------
# The intent queue
# --------------------------------------------------------------------------


def test_pending_intents_excludes_acknowledged_rows(store_file: Path) -> None:
    with Store.open(store_file):
        pass
    _stage_intent(store_file, "i-1")
    _stage_intent(store_file, "i-2")

    with Store.open(store_file) as store:
        acknowledged = store.acknowledge_message("i-1", acknowledged_by="runner")
        pending = store.pending_intents(PROJECT)

    assert acknowledged.is_acknowledged
    assert acknowledged.acknowledged_by == "runner"
    assert [message.id for message in pending] == ["i-2"]


def test_second_acknowledge_raises(store_file: Path) -> None:
    with Store.open(store_file):
        pass
    _stage_intent(store_file, "i-1")

    with Store.open(store_file) as store:
        store.acknowledge_message("i-1", acknowledged_by="runner")

        with pytest.raises(InvalidTransitionError):
            store.acknowledge_message("i-1", acknowledged_by="someone-else")

        [row] = store.messages(PROJECT, channel=Channel.INTENT)
        assert row.acknowledged_by == "runner"


def test_acknowledging_an_escalation_raises(store_file: Path) -> None:
    with Store.open(store_file) as store:
        store.block(_make_node(store), kind=BlockedKind.HUMAN, context="c")
        [escalation] = store.messages(PROJECT, channel=Channel.ESCALATION)

        with pytest.raises(InvalidTransitionError):
            store.acknowledge_message(escalation.id, acknowledged_by="runner")


def test_acknowledging_an_unknown_message_raises(store_file: Path) -> None:
    with Store.open(store_file) as store:
        with pytest.raises(InvalidTransitionError):
            store.acknowledge_message("no-such-message", acknowledged_by="runner")
