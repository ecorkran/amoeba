"""Deliveries: sequence numbers and the highest ever assigned (240 D5, D7)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.deliveries import (
    NONE_ASSIGNED,
    deliveries_since,
    highest_assigned_seq,
    write_delivery,
)
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent
from store.message_support import (
    ADDRESSEE,
    NOW,
    SENDER,
    THIRD,
    delivery_rows,
    seed_members,
    send_request,
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, SENDER, ADDRESSEE, THIRD)
            send_request(transaction, "first")
        yield opened


def test_nothing_was_ever_assigned_reads_zero(store: Store) -> None:
    with store.read() as transaction:
        assert highest_assigned_seq(transaction) == NONE_ASSIGNED == 0


def test_seq_increases_across_writers_in_separate_transactions(store: Store) -> None:
    for member in (ADDRESSEE, THIRD, ADDRESSEE):
        with store.write() as transaction:
            write_delivery(transaction, member, "first", DeliveryEvent.SENT, NOW)

    with store.read() as transaction:
        assert [row[0] for row in delivery_rows(transaction)] == [1, 2, 3]
        assert highest_assigned_seq(transaction) == 3


def test_the_highest_seq_does_not_fall_when_rows_are_deleted(store: Store) -> None:
    with store.write() as transaction:
        write_delivery(transaction, ADDRESSEE, "first", DeliveryEvent.SENT, NOW)
        write_delivery(transaction, ADDRESSEE, "first", DeliveryEvent.ACCEPTED, NOW)
    with store.write() as transaction:
        transaction.execute("DELETE FROM deliveries")

    with store.read() as transaction:
        assert delivery_rows(transaction) == []
        assert highest_assigned_seq(transaction) == 2
    with store.write() as transaction:
        write_delivery(transaction, ADDRESSEE, "first", DeliveryEvent.DONE, NOW)
    with store.read() as transaction:
        assert [row[0] for row in delivery_rows(transaction)] == [3]


def test_deliveries_since_is_one_members_rows_after_the_cursor_in_order(
    store: Store,
) -> None:
    with store.write() as transaction:
        write_delivery(transaction, ADDRESSEE, "first", DeliveryEvent.SENT, NOW)
        write_delivery(transaction, THIRD, "first", DeliveryEvent.SENT, NOW)
        write_delivery(transaction, ADDRESSEE, "first", DeliveryEvent.CANCELLED, NOW)

    with store.read() as transaction:
        everything = deliveries_since(transaction, ADDRESSEE, 0)
        later = deliveries_since(transaction, ADDRESSEE, 1)

    assert [(d.seq, d.event) for d in everything] == [
        (1, DeliveryEvent.SENT),
        (3, DeliveryEvent.CANCELLED),
    ]
    assert [d.seq for d in later] == [3]
    assert everything[0].message_id == "first"
    assert everything[0].created_at == NOW
