"""Push reads: the member's high seq and the rows above it (slice 241, D2, D4, 3.5)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.store.deliveries import write_delivery
from amoeba.store.models import PushRow
from amoeba.store.push_reads import NO_DELIVERY_SEQ, member_high_seq, push_rows_after
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, MessageKind
from store.message_support import (
    ADDRESSEE,
    NOW,
    SENDER,
    THIRD,
    count,
    insert_raw_note,
    seed_members,
    send_request,
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, SENDER, ADDRESSEE, THIRD)
            send_request(transaction, "req")
            insert_raw_note(transaction, "note", changed=NOW)
        yield opened


def _deliver(store: Store, *deliveries: tuple[str, str, DeliveryEvent]) -> None:
    with store.write() as transaction:
        for member, message, event in deliveries:
            write_delivery(transaction, member, message, event, NOW)


def test_a_member_with_no_delivery_reads_the_baseline_value(store: Store) -> None:
    with store.read() as transaction:
        assert member_high_seq(transaction, ADDRESSEE) == NO_DELIVERY_SEQ


def test_the_high_seq_counts_only_the_members_own_rows(store: Store) -> None:
    _deliver(
        store,
        (ADDRESSEE, "req", DeliveryEvent.SENT),
        (SENDER, "req", DeliveryEvent.ACCEPTED),
        (ADDRESSEE, "req", DeliveryEvent.CANCELLED),
        (THIRD, "req", DeliveryEvent.SENT),
    )

    with store.read() as transaction:
        assert member_high_seq(transaction, ADDRESSEE) == 3
        assert member_high_seq(transaction, SENDER) == 2
        assert member_high_seq(transaction, THIRD) == 4


def test_rows_above_the_number_in_order_with_their_counterparty(store: Store) -> None:
    _deliver(
        store,
        (ADDRESSEE, "req", DeliveryEvent.SENT),
        (SENDER, "req", DeliveryEvent.ACCEPTED),
        (ADDRESSEE, "note", DeliveryEvent.SENT),
        (ADDRESSEE, "req", DeliveryEvent.CANCELLED),
    )

    with store.read() as transaction:
        received = push_rows_after(transaction, ADDRESSEE, 0)
        later = push_rows_after(transaction, ADDRESSEE, 1)
        accepted = push_rows_after(transaction, SENDER, 0)

    assert received == (
        PushRow(1, DeliveryEvent.SENT, MessageKind.REQUEST, SENDER),
        PushRow(3, DeliveryEvent.SENT, MessageKind.NOTE, SENDER),
        PushRow(4, DeliveryEvent.CANCELLED, MessageKind.REQUEST, SENDER),
    )
    assert [row.seq for row in later] == [3, 4]
    # The sender learns of the acceptance; its counterparty is the other party.
    assert accepted == (
        PushRow(2, DeliveryEvent.ACCEPTED, MessageKind.REQUEST, ADDRESSEE),
    )


def test_the_reads_write_nothing(store: Store) -> None:
    _deliver(store, (ADDRESSEE, "req", DeliveryEvent.SENT))

    def state() -> tuple[object, ...]:
        with store.read() as transaction:
            sequence = transaction.execute(
                "SELECT name, seq FROM sqlite_sequence ORDER BY name"
            ).fetchall()
            tables = ("deliveries", "messages", "sessions", "members")
            return (*(count(transaction, table) for table in tables), sequence)

    before = state()
    with store.read() as transaction:
        member_high_seq(transaction, ADDRESSEE)
        push_rows_after(transaction, ADDRESSEE, 0)

    assert state() == before
