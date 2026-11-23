"""The sweep: expiry is recorded once, old terminal rows are pruned (240 D6)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store import sql_messages
from amoeba.store.message_rejections import record_rejection
from amoeba.store.message_sweep import sweep, sweep_due
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import get_message
from amoeba.store.notes import NewNote, insert_note
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, RequestState, WakeOutcome
from amoeba.store.wakes import finish_wake
from store.message_support import (
    ADDRESSEE,
    NOW,
    SENDER,
    TTL,
    count,
    delivery_rows,
    insert_raw_note,
    seed_members,
    send_request,
)
from store.wake_support import claim, give_checkout_command

RETENTION_DAYS = 30
PAST_TTL = NOW + TTL + timedelta(seconds=1)
LONG_AFTER = NOW + timedelta(days=RETENTION_DAYS + 1)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, SENDER, ADDRESSEE)
        yield opened


def _end(store: Store, message_id: str, state: RequestState, when: datetime) -> None:
    with store.write() as transaction:
        message = get_message(transaction, message_id)
        assert message is not None
        change_state(
            transaction,
            message,
            state,
            DeliveryEvent(state.value),
            ADDRESSEE,
            when,
            StateFields(),
        )


def _sweep(store: Store, when: datetime) -> None:
    with store.write() as transaction:
        sweep(transaction, when, RETENTION_DAYS)


def _ids(store: Store) -> set[str]:
    with store.read() as transaction:
        return {
            str(row[0])
            for row in transaction.execute("SELECT message_id FROM messages")
        }


def test_expiry_writes_the_state_and_both_deliveries_once(store: Store) -> None:
    with store.write() as transaction:
        send_request(transaction, "first")

    _sweep(store, PAST_TTL)
    with store.read() as transaction:
        message = get_message(transaction, "first")
        first_pass = delivery_rows(transaction)
    _sweep(store, PAST_TTL + timedelta(hours=1))
    with store.read() as transaction:
        second_pass = delivery_rows(transaction)

    assert message is not None
    assert message.state is RequestState.EXPIRED
    assert message.state_changed_at == PAST_TTL
    assert message.reason is None
    assert [(row[1], row[3]) for row in first_pass] == [
        (SENDER, "expired"),
        (ADDRESSEE, "expired"),
    ]
    assert second_pass == first_pass


def test_a_request_not_yet_due_is_not_expired(store: Store) -> None:
    with store.write() as transaction:
        send_request(transaction, "first")

    _sweep(store, NOW + TTL - timedelta(seconds=1))

    with store.read() as transaction:
        message = get_message(transaction, "first")
    assert message is not None
    assert message.state is RequestState.OPEN


def test_open_and_accepted_requests_are_never_pruned(store: Store) -> None:
    with store.write() as transaction:
        send_request(transaction, "open-one")
        send_request(transaction, "accepted-one")
    _end(store, "accepted-one", RequestState.ACCEPTED, NOW)

    # Past retention, but an open request expires first and then stands in the
    # table for a full retention period of its own.
    _sweep(store, NOW + TTL - timedelta(seconds=1) + timedelta(days=100))
    with store.read() as transaction:
        accepted = get_message(transaction, "accepted-one")
    assert accepted is not None
    assert accepted.state is RequestState.ACCEPTED
    assert "accepted-one" in _ids(store)


def test_old_terminal_requests_and_their_deliveries_are_pruned_young_kept(
    store: Store,
) -> None:
    with store.write() as transaction:
        send_request(transaction, "old")
        send_request(transaction, "young")
    _end(store, "old", RequestState.DONE, NOW)
    _end(store, "young", RequestState.DECLINED, LONG_AFTER - timedelta(days=1))

    _sweep(store, LONG_AFTER)

    assert _ids(store) == {"young"}
    with store.read() as transaction:
        assert {row[2] for row in delivery_rows(transaction)} == {"young"}


def test_old_rejection_rows_are_pruned_young_kept(store: Store) -> None:
    with store.write() as transaction:
        for stamp in (NOW, LONG_AFTER - timedelta(days=1)):
            record_rejection(
                transaction, SENDER, "send", "to", None, None, "malformed", "d", stamp
            )

    _sweep(store, LONG_AFTER)

    with store.read() as transaction:
        assert count(transaction, "message_rejections") == 1


def test_the_request_prune_leaves_a_note_alone(store: Store) -> None:
    # A young note: 243's note prune removes an aged one (tested below).
    with store.write() as transaction:
        insert_raw_note(transaction, "note-1", changed=LONG_AFTER)

    _sweep(store, LONG_AFTER)

    assert _ids(store) == {"note-1"}


def test_sweep_due_is_false_on_a_quiet_store(store: Store) -> None:
    with store.write() as transaction:
        send_request(transaction, "first")
    _end(store, "first", RequestState.ACCEPTED, NOW)

    with store.read() as transaction:
        assert not sweep_due(transaction, NOW + timedelta(days=1), RETENTION_DAYS)


def test_sweep_due_is_true_for_each_due_kind(store: Store) -> None:
    with store.write() as transaction:
        send_request(transaction, "expiring")
        send_request(transaction, "ended")
        record_rejection(
            transaction, SENDER, "send", None, None, None, "malformed", "d", NOW
        )
    _end(store, "ended", RequestState.DONE, NOW)

    with store.read() as transaction:
        assert sweep_due(transaction, PAST_TTL, RETENTION_DAYS)  # an expiry
    _sweep(store, PAST_TTL)

    # Only the ended request and the rejection remain due: one prune kind each.
    with store.write() as transaction:
        transaction.execute("DELETE FROM message_rejections")
    with store.read() as transaction:
        assert sweep_due(transaction, LONG_AFTER, RETENTION_DAYS)  # a request to prune
    with store.write() as transaction:
        transaction.execute("DELETE FROM deliveries")
        transaction.execute("DELETE FROM messages")
        record_rejection(
            transaction, SENDER, "send", None, None, None, "malformed", "d", NOW
        )
    with store.read() as transaction:
        assert sweep_due(transaction, LONG_AFTER, RETENTION_DAYS)  # a rejection


def _write_note(store: Store, message_id: str, when: datetime) -> None:
    """A direct note from the sender to the addressee, with its delivery."""
    note = NewNote(message_id, SENDER, ADDRESSEE, None, "subject", "body")
    with store.write() as transaction:
        insert_note(transaction, note, [ADDRESSEE], when)


def test_an_aged_note_is_pruned_with_its_deliveries_read_or_not(store: Store) -> None:
    _write_note(store, "old-note", NOW)
    _write_note(store, "young-note", LONG_AFTER)

    _sweep(store, LONG_AFTER)

    assert _ids(store) == {"young-note"}
    with store.read() as transaction:
        assert [row[2] for row in delivery_rows(transaction)] == ["young-note"]
        assert transaction.execute("PRAGMA foreign_key_check").fetchall() == []


def test_the_expire_step_never_changes_a_note(store: Store) -> None:
    _write_note(store, "a-note", NOW)

    _sweep(store, NOW + timedelta(days=RETENTION_DAYS - 1))

    with store.read() as transaction:
        note = get_message(transaction, "a-note")
        assert note is not None and note.state is None
        assert [row[3] for row in delivery_rows(transaction)] == ["sent"]


def test_the_note_prune_leaves_open_and_accepted_requests_alone(store: Store) -> None:
    _write_note(store, "old-note", NOW)
    with store.write() as transaction:
        send_request(transaction, "open-one", now=LONG_AFTER)
        send_request(transaction, "accepted-one", now=LONG_AFTER)
    _end(store, "accepted-one", RequestState.ACCEPTED, LONG_AFTER)

    _sweep(store, LONG_AFTER)

    assert _ids(store) == {"open-one", "accepted-one"}


def test_sweep_due_is_true_for_an_aged_note_alone_and_false_for_a_young_one(
    store: Store,
) -> None:
    _write_note(store, "a-note", NOW)
    with store.read() as transaction:
        assert not sweep_due(transaction, NOW + timedelta(days=1), RETENTION_DAYS)
        assert sweep_due(transaction, LONG_AFTER, RETENTION_DAYS)


def test_the_due_check_searches_an_index_and_never_scans_messages(
    store: Store,
) -> None:
    """The note clause must use ``messages_state_expires`` (notes have a null state),
    not walk every message, on each read-then-write path."""
    with store.read() as transaction:
        plan = " ".join(
            str(row[3])
            for row in transaction.execute(
                f"EXPLAIN QUERY PLAN {sql_messages.SELECT_SWEEP_DUE}",
                ("x", "x", "x", "x"),
            )
        )

    assert "SCAN messages" not in plan


# --- wakes rows (slice 244, D10) ----------------------------------------------


def _claim_wake_at(store: Store, wake_id: str, when: datetime) -> None:
    """A claimed, unended wake row started at ``when`` for the addressee."""
    with store.write() as transaction:
        give_checkout_command(transaction, ADDRESSEE, "wake-agent")
        claimed = claim(transaction, wake_id, now=when, max_wakes=100)
        assert claimed is not None


def _wake_ids(store: Store) -> set[str]:
    with store.read() as transaction:
        return {str(row[0]) for row in transaction.execute("SELECT wake_id FROM wakes")}


def test_the_sweep_deletes_an_aged_wake_row_ended_or_not_and_keeps_a_young_one(
    store: Store,
) -> None:
    _claim_wake_at(store, "unended-aged", NOW)
    _claim_wake_at(store, "ended-aged", NOW + timedelta(hours=1))
    with store.write() as transaction:
        finish_wake(
            transaction,
            "ended-aged",
            WakeOutcome.EXITED,
            0,
            None,
            NOW + timedelta(hours=2),
        )
    _claim_wake_at(store, "young", LONG_AFTER - timedelta(days=1))

    _sweep(store, LONG_AFTER)

    assert _wake_ids(store) == {"young"}


def test_sweep_due_is_true_for_an_aged_wake_row_alone_and_false_for_a_young_one(
    store: Store,
) -> None:
    _claim_wake_at(store, "only-row", NOW)

    with store.read() as transaction:
        young = sweep_due(transaction, NOW + timedelta(days=1), RETENTION_DAYS)
        aged = sweep_due(transaction, LONG_AFTER, RETENTION_DAYS)

    assert (young, aged) == (False, True)
