"""``change_state``: the one state writer and who it tells (240 D5)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from store_open import open_local_store

from amoeba.store import message_transitions
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import get_message
from amoeba.store.programs import remove_member
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import DeliveryEvent, RequestState
from store.message_support import (
    ADDRESSEE,
    NOW,
    SENDER,
    delivery_rows,
    insert_raw_note,
    seed_members,
    send_request,
)

LATER = NOW + timedelta(hours=1)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, SENDER, ADDRESSEE)
            send_request(transaction, "first")
        yield opened


def _change(
    store: Store,
    state: RequestState,
    event: DeliveryEvent,
    actor: str | None,
    fields: StateFields | None = None,
) -> None:
    with store.write() as transaction:
        message = get_message(transaction, "first")
        assert message is not None
        change_state(
            transaction,
            message,
            state,
            event,
            actor,
            LATER,
            StateFields() if fields is None else fields,
        )


def _delivered(store: Store) -> list[tuple[str, str]]:
    with store.read() as transaction:
        return [(row[1], row[3]) for row in delivery_rows(transaction)]


@pytest.mark.parametrize(
    ("state", "event"),
    [
        (RequestState.ACCEPTED, DeliveryEvent.ACCEPTED),
        (RequestState.DECLINED, DeliveryEvent.DECLINED),
        (RequestState.DONE, DeliveryEvent.DONE),
    ],
)
def test_a_reply_by_the_addressee_reaches_the_sender(
    store: Store, state: RequestState, event: DeliveryEvent
) -> None:
    _change(store, state, event, ADDRESSEE)

    assert _delivered(store) == [(SENDER, event.value)]


def test_cancel_by_the_sender_reaches_the_addressee(store: Store) -> None:
    _change(store, RequestState.CANCELLED, DeliveryEvent.CANCELLED, SENDER)

    assert _delivered(store) == [(ADDRESSEE, "cancelled")]


@pytest.mark.parametrize(
    ("state", "event"),
    [
        (RequestState.CANCELLED, DeliveryEvent.CANCELLED),
        (RequestState.EXPIRED, DeliveryEvent.EXPIRED),
    ],
)
def test_an_unknown_actor_and_expiry_reach_both(
    store: Store, state: RequestState, event: DeliveryEvent
) -> None:
    _change(store, state, event, None)

    assert _delivered(store) == [(SENDER, event.value), (ADDRESSEE, event.value)]


def test_a_request_to_its_own_sender_is_told_once(store: Store) -> None:
    with store.write() as transaction:
        send_request(transaction, "own", to_member=SENDER)
        message = get_message(transaction, "own")
        assert message is not None
        change_state(
            transaction,
            message,
            RequestState.EXPIRED,
            DeliveryEvent.EXPIRED,
            None,
            LATER,
            StateFields(),
        )

    assert _delivered(store) == [(SENDER, "expired")]


def test_a_removed_party_gets_nothing(store: Store) -> None:
    with store.write() as transaction:
        assert remove_member(transaction, SENDER, NOW)

    _change(store, RequestState.CANCELLED, DeliveryEvent.CANCELLED, None)

    assert _delivered(store) == [(ADDRESSEE, "cancelled")]


def test_the_change_writes_the_state_its_fields_and_the_time(store: Store) -> None:
    _change(
        store,
        RequestState.ACCEPTED,
        DeliveryEvent.ACCEPTED,
        ADDRESSEE,
        StateFields(accepted_at=LATER),
    )
    _change(
        store,
        RequestState.DONE,
        DeliveryEvent.DONE,
        ADDRESSEE,
        StateFields(result="all of it", result_commit="c" * 40, result_version="v1"),
    )

    with store.read() as transaction:
        message = get_message(transaction, "first")

    assert message is not None
    assert message.state is RequestState.DONE
    assert message.state_changed_at == LATER
    # An earlier field survives a later change that does not name it.
    assert message.accepted_at == LATER
    assert (message.result, message.result_commit, message.result_version) == (
        "all of it",
        "c" * 40,
        "v1",
    )


def test_a_failure_after_the_first_delivery_leaves_no_change_and_no_delivery(
    store: Store, monkeypatch: MonkeyPatch
) -> None:
    real = message_transitions.write_delivery
    calls: list[str] = []

    def fail_on_the_second(
        transaction: Transaction,
        member_id: str,
        message_id: str,
        event: DeliveryEvent,
        now: datetime,
    ) -> None:
        calls.append("call")
        if len(calls) == 2:
            raise RuntimeError("forced")
        real(transaction, member_id, message_id, event, now)

    monkeypatch.setattr(message_transitions, "write_delivery", fail_on_the_second)

    with pytest.raises(RuntimeError, match="forced"):
        _change(store, RequestState.EXPIRED, DeliveryEvent.EXPIRED, None)

    assert len(calls) == 2
    assert _delivered(store) == []
    with store.read() as transaction:
        message = get_message(transaction, "first")
    assert message is not None
    assert message.state is RequestState.OPEN


def test_a_note_has_no_state_to_change(store: Store) -> None:
    with store.write() as transaction:
        insert_raw_note(transaction, "note-1", changed=NOW)
        note = get_message(transaction, "note-1")
        assert note is not None
        with pytest.raises(ValueError, match="not a request"):
            change_state(
                transaction,
                note,
                RequestState.CANCELLED,
                DeliveryEvent.CANCELLED,
                None,
                LATER,
                StateFields(),
            )
