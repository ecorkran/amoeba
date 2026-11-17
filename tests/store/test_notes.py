"""``store.notes``: insert, read by delivery and prune (slice 243, D1, D2, D6)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from amoeba.store import notes
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import get_message
from amoeba.store.notes import (
    NewNote,
    insert_note,
    prune_notes,
    prune_oldest_notes_from,
    received_notes,
)
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import DeliveryEvent, MessageKind, RequestState
from store.message_support import (
    ADDRESSEE,
    NOW,
    PROGRAM,
    SENDER,
    THIRD,
    count,
    delivery_rows,
    seed_members,
    send_request,
)

LATER = NOW + timedelta(hours=1)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, SENDER, ADDRESSEE, THIRD)
        yield opened


def _direct(message_id: str) -> NewNote:
    return NewNote(message_id, SENDER, ADDRESSEE, None, "a subject", "a body")


def _program(message_id: str) -> NewNote:
    return NewNote(message_id, SENDER, None, PROGRAM, "a subject", "a body")


def test_insert_note_to_a_member_writes_one_row_and_one_sent_delivery(
    store: Store,
) -> None:
    with store.write() as transaction:
        stored = insert_note(transaction, _direct("note-1"), [ADDRESSEE], NOW)
    with store.read() as transaction:
        row = transaction.execute(
            "SELECT kind, state, expires_at, depth, created_at, state_changed_at, "
            "to_member, to_program FROM messages WHERE message_id = 'note-1'"
        ).fetchone()
        deliveries = delivery_rows(transaction)
    stamp = encode_timestamp(NOW)
    assert row == ("note", None, None, 1, stamp, stamp, ADDRESSEE, None)
    assert deliveries == [(1, ADDRESSEE, "note-1", "sent")]
    assert stored.kind is MessageKind.NOTE
    assert stored.state is None
    assert stored.state_changed_at == stored.created_at == NOW


def test_insert_note_to_a_program_writes_one_row_and_a_delivery_each(
    store: Store,
) -> None:
    with store.write() as transaction:
        insert_note(transaction, _program("note-1"), [ADDRESSEE, THIRD], NOW)
    with store.read() as transaction:
        row = transaction.execute(
            "SELECT to_member, to_program FROM messages"
        ).fetchall()
        deliveries = delivery_rows(transaction)
        assert count(transaction, "messages") == 1
    assert row == [(None, PROGRAM)]
    assert deliveries == [
        (1, ADDRESSEE, "note-1", "sent"),
        (2, THIRD, "note-1", "sent"),
    ]


def test_a_failure_after_the_first_delivery_leaves_no_row_and_no_delivery(
    store: Store,
) -> None:
    real = notes.write_delivery
    calls: list[str] = []

    def fail_on_second(
        transaction: Transaction,
        member_id: str,
        message_id: str,
        event: DeliveryEvent,
        now: datetime,
    ) -> None:
        calls.append("call")
        if len(calls) == 2:
            raise RuntimeError("second delivery fails")
        real(transaction, member_id, message_id, event, now)

    with (
        patch.object(notes, "write_delivery", fail_on_second),
        pytest.raises(RuntimeError, match="second delivery"),
        store.write() as transaction,
    ):
        insert_note(transaction, _program("note-1"), [ADDRESSEE, THIRD], NOW)
    with store.read() as transaction:
        assert count(transaction, "messages") == 0
        assert count(transaction, "deliveries") == 0


def test_received_notes_returns_what_the_member_has_a_delivery_for(
    store: Store,
) -> None:
    with store.write() as transaction:
        insert_note(transaction, _direct("to-addressee"), [ADDRESSEE], NOW)
        insert_note(transaction, _program("to-program"), [ADDRESSEE, THIRD], NOW)
        send_request(transaction, "a-request")
    with store.read() as transaction:
        addressee = received_notes(transaction, ADDRESSEE, None)
        third = received_notes(transaction, THIRD, None)
        sender = received_notes(transaction, SENDER, None)
    assert [item.note.message_id for item in addressee] == [
        "to-addressee",
        "to-program",
    ]
    assert [item.note.message_id for item in third] == ["to-program"]
    assert sender == ()
    assert {item.delivery.event for item in addressee} == {DeliveryEvent.SENT}
    assert [item.delivery.member_id for item in addressee] == [ADDRESSEE, ADDRESSEE]


def test_received_notes_honours_since_by_delivery_seq(store: Store) -> None:
    with store.write() as transaction:
        insert_note(transaction, _direct("first"), [ADDRESSEE], NOW)
        insert_note(transaction, _direct("second"), [ADDRESSEE], NOW)
        insert_note(transaction, _direct("third"), [ADDRESSEE], NOW)
    with store.read() as transaction:
        after_one = received_notes(transaction, ADDRESSEE, 1)
        after_all = received_notes(transaction, ADDRESSEE, 3)
    assert [item.note.message_id for item in after_one] == ["second", "third"]
    assert [item.delivery.seq for item in after_one] == [2, 3]
    assert after_all == ()


def test_a_program_note_comes_back_once_for_each_recipient(store: Store) -> None:
    with store.write() as transaction:
        insert_note(transaction, _program("shared"), [ADDRESSEE, THIRD], NOW)
    with store.read() as transaction:
        assert len(received_notes(transaction, ADDRESSEE, None)) == 1
        assert len(received_notes(transaction, THIRD, None)) == 1


def test_prune_notes_deletes_an_old_note_with_its_deliveries(store: Store) -> None:
    with store.write() as transaction:
        insert_note(transaction, _program("old"), [ADDRESSEE, THIRD], NOW)
        insert_note(transaction, _direct("young"), [ADDRESSEE], LATER)
    with store.write() as transaction:
        pruned = prune_notes(transaction, encode_timestamp(NOW + timedelta(minutes=1)))
    with store.read() as transaction:
        remaining = [
            row[0] for row in transaction.execute("SELECT message_id FROM messages")
        ]
        deliveries = delivery_rows(transaction)
        assert transaction.execute("PRAGMA foreign_key_check").fetchall() == []
    assert pruned == 1
    assert remaining == ["young"]
    assert deliveries == [(3, ADDRESSEE, "young", "sent")]


def test_prune_notes_never_touches_requests(store: Store) -> None:
    with store.write() as transaction:
        send_request(transaction, "open-one")
        send_request(transaction, "accepted-one")
        send_request(transaction, "done-one")
        for message_id, state in (
            ("accepted-one", RequestState.ACCEPTED),
            ("done-one", RequestState.DONE),
        ):
            message = get_message(transaction, message_id)
            assert message is not None
            change_state(
                transaction,
                message,
                state,
                DeliveryEvent(state.value),
                ADDRESSEE,
                NOW,
                StateFields(),
            )
    with store.write() as transaction:
        pruned = prune_notes(transaction, encode_timestamp(NOW + timedelta(days=400)))
    with store.read() as transaction:
        assert count(transaction, "messages") == 3
    assert pruned == 0


def test_prune_oldest_notes_from_keeps_that_senders_newest_and_nothing_else_goes(
    store: Store,
) -> None:
    with store.write() as transaction:
        insert_note(transaction, _direct("oldest"), [ADDRESSEE], NOW)
        insert_note(transaction, _program("middle"), [ADDRESSEE, THIRD], LATER)
        insert_note(
            transaction, _direct("newest"), [ADDRESSEE], LATER + timedelta(hours=1)
        )
        theirs = NewNote("theirs", ADDRESSEE, SENDER, None, "a subject", "a body")
        insert_note(transaction, theirs, [SENDER], NOW)
        send_request(transaction, "ask")
    with store.write() as transaction:
        prune_oldest_notes_from(transaction, SENDER, 1)
    with store.read() as transaction:
        remaining = sorted(
            row[0] for row in transaction.execute("SELECT message_id FROM messages")
        )
        delivered = {row[2] for row in delivery_rows(transaction)}
        assert transaction.execute("PRAGMA foreign_key_check").fetchall() == []
    assert remaining == ["ask", "newest", "theirs"]
    assert not {"oldest", "middle"} & delivered
    assert {"newest", "theirs"} <= delivered
