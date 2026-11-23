"""Requests in the store: the by-id read, the effective state, the insert (240 D4)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.deliveries import write_delivery
from amoeba.store.errors import StoreRowError
from amoeba.store.messages import (
    effective_state,
    get_message,
    live_children_of_member,
    prune_oldest_finished_from,
    request_counts_from,
)
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, MessageKind, RequestState
from store.message_support import (
    ADDRESSEE,
    NOW,
    SENDER,
    TTL,
    delivery_rows,
    insert_raw_note,
    seed_members,
    send_request,
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, SENDER, ADDRESSEE)
        yield opened


def test_an_inserted_request_reads_back_with_every_column(store: Store) -> None:
    with store.write() as transaction:
        inserted = send_request(transaction, "first")

    with store.read() as transaction:
        read = get_message(transaction, "first")

    assert read == inserted
    assert read is not None
    assert read.kind is MessageKind.REQUEST
    assert (read.from_member, read.to_member, read.to_program) == (
        SENDER,
        ADDRESSEE,
        None,
    )
    assert (read.parent_id, read.depth) == (None, 1)
    assert (read.subject, read.body) == ("subject of first", "body of first")
    assert read.state is RequestState.OPEN
    assert (read.result, read.result_commit, read.result_version, read.reason) == (
        None,
        None,
        None,
        None,
    )
    assert read.accepted_at is None
    assert (read.created_at, read.state_changed_at) == (NOW, NOW)
    assert read.expires_at == NOW + TTL


def test_depth_is_the_parents_plus_one(store: Store) -> None:
    with store.write() as transaction:
        child = send_request(transaction, "child", parent_id="parent", parent_depth=2)

    assert (child.parent_id, child.depth) == ("parent", 3)


def test_an_unknown_id_returns_none(store: Store) -> None:
    with store.read() as transaction:
        assert get_message(transaction, "nobody") is None


def test_an_open_request_reads_expired_at_its_expiry_and_not_before(
    store: Store,
) -> None:
    with store.write() as transaction:
        request = send_request(transaction, "first")

    assert request.expires_at is not None
    assert effective_state(request, request.expires_at - timedelta(seconds=1)) is (
        RequestState.OPEN
    )
    assert effective_state(request, request.expires_at) is RequestState.EXPIRED


def test_an_accepted_request_never_expires(store: Store) -> None:
    with store.write() as transaction:
        request = send_request(transaction, "first")
    accepted = replace(request, state=RequestState.ACCEPTED)

    assert effective_state(accepted, NOW + timedelta(days=3650)) is (
        RequestState.ACCEPTED
    )


@pytest.mark.parametrize("state", sorted(RequestState.terminal()))
def test_a_terminal_state_is_unchanged(store: Store, state: RequestState) -> None:
    with store.write() as transaction:
        request = send_request(transaction, "first")

    assert effective_state(replace(request, state=state), NOW + 10 * TTL) is state


def test_a_note_has_no_state(store: Store) -> None:
    with store.write() as transaction:
        insert_raw_note(transaction, "note-1", changed=NOW)
        note = get_message(transaction, "note-1")

    assert note is not None
    assert note.kind is MessageKind.NOTE
    with pytest.raises(StoreRowError, match="is a note"):
        effective_state(note, NOW + 10 * TTL)


def test_live_children_of_member_lists_each_live_childs_id_under_its_parent(
    store: Store,
) -> None:
    with store.write() as transaction:
        send_request(transaction, "root")
        send_request(transaction, "first", parent_id="root", parent_depth=1)
        send_request(transaction, "second", parent_id="root", parent_depth=1)
        send_request(transaction, "ended", parent_id="root", parent_depth=1)
        transaction.execute(
            "UPDATE messages SET state = 'done' WHERE message_id = 'ended'"
        )
        send_request(transaction, "grandchild", parent_id="first", parent_depth=2)
        send_request(
            transaction,
            "elsewhere",
            from_member=ADDRESSEE,
            to_member=ADDRESSEE,
        )
        send_request(
            transaction,
            "elsewhere-child",
            from_member=ADDRESSEE,
            to_member=ADDRESSEE,
            parent_id="elsewhere",
            parent_depth=1,
        )

    with store.read() as transaction:
        children = live_children_of_member(transaction, SENDER)

    assert children == {"root": ("first", "second"), "first": ("grandchild",)}


def test_request_counts_split_a_senders_requests_into_all_and_live(
    store: Store,
) -> None:
    with store.write() as transaction:
        send_request(transaction, "open")
        send_request(transaction, "accepted")
        send_request(transaction, "done")
        send_request(transaction, "other", from_member=ADDRESSEE, to_member=SENDER)
        transaction.execute(
            "UPDATE messages SET state = 'accepted' WHERE message_id = 'accepted'"
        )
        transaction.execute(
            "UPDATE messages SET state = 'done' WHERE message_id = 'done'"
        )

    with store.read() as transaction:
        assert request_counts_from(transaction, SENDER) == (3, 2)
        assert request_counts_from(transaction, ADDRESSEE) == (1, 1)
        assert request_counts_from(transaction, "nobody") == (0, 0)


def test_the_oldest_finished_requests_go_with_their_deliveries_and_live_ones_stay(
    store: Store,
) -> None:
    with store.write() as transaction:
        for number, name in enumerate(("old", "newer", "live")):
            send_request(transaction, name, now=NOW + timedelta(minutes=number))
            write_delivery(transaction, ADDRESSEE, name, DeliveryEvent.SENT, NOW)
        for name, minutes in (("old", 10), ("newer", 20)):
            transaction.execute(
                "UPDATE messages SET state = 'done', state_changed_at = ? "
                "WHERE message_id = ?",
                (encode_timestamp(NOW + timedelta(minutes=minutes)), name),
            )

        prune_oldest_finished_from(transaction, SENDER, 1)

        assert get_message(transaction, "old") is None
        assert get_message(transaction, "newer") is not None
        assert get_message(transaction, "live") is not None
        assert [row[2] for row in delivery_rows(transaction)] == ["newer", "live"]
