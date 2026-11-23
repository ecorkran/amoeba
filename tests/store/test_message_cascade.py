"""``cancel_member_requests``: removing a member cancels its live requests (240 D10)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.message_transitions import (
    MEMBER_REMOVED_REASON,
    StateFields,
    cancel_member_requests,
    change_state,
)
from amoeba.store.messages import get_message
from amoeba.store.models import MemberSettings
from amoeba.store.programs import remove_member, upsert_member
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, RequestState, RulesFrom
from store.message_support import (
    ADDRESSEE,
    NOW,
    PROGRAM,
    SENDER,
    delivery_rows,
    seed_members,
    send_request,
)

LATER = NOW + timedelta(hours=1)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, SENDER, ADDRESSEE)
            send_request(transaction, "open-one")
            send_request(transaction, "accepted-one")
            send_request(transaction, "done-one")
        yield opened


def _move(store: Store, message_id: str, state: RequestState) -> None:
    with store.write() as transaction:
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


def _states(store: Store) -> dict[str, tuple[RequestState | None, str | None]]:
    with store.read() as transaction:
        messages = [
            get_message(transaction, name)
            for name in ("open-one", "accepted-one", "done-one")
        ]
    return {m.message_id: (m.state, m.reason) for m in messages if m is not None}


@pytest.mark.parametrize("removed", [SENDER, ADDRESSEE])
def test_removing_either_party_cancels_live_requests_and_tells_the_survivor(
    store: Store, removed: str
) -> None:
    survivor = ADDRESSEE if removed == SENDER else SENDER
    _move(store, "accepted-one", RequestState.ACCEPTED)
    _move(store, "done-one", RequestState.DONE)
    with store.read() as transaction:
        deliveries_before = len(delivery_rows(transaction))

    with store.write() as transaction:
        assert remove_member(transaction, removed, LATER)
        cancel_member_requests(transaction, removed, LATER)

    states = _states(store)
    assert states["open-one"] == (RequestState.CANCELLED, MEMBER_REMOVED_REASON)
    assert states["accepted-one"] == (RequestState.CANCELLED, MEMBER_REMOVED_REASON)
    assert states["done-one"] == (RequestState.DONE, None)
    with store.read() as transaction:
        new = delivery_rows(transaction)[deliveries_before:]
    assert sorted((row[1], row[2], row[3]) for row in new) == [
        (survivor, "accepted-one", "cancelled"),
        (survivor, "open-one", "cancelled"),
    ]


def test_a_member_with_no_live_request_changes_nothing(store: Store) -> None:
    with store.write() as transaction:
        cancel_member_requests(transaction, "no-requests-member", LATER)

    assert _states(store)["open-one"] == (RequestState.OPEN, None)


def test_a_re_registered_member_keeps_its_retained_history(store: Store) -> None:
    with store.write() as transaction:
        assert remove_member(transaction, ADDRESSEE, LATER)
        cancel_member_requests(transaction, ADDRESSEE, LATER)
        previous = get_message(transaction, "open-one")
    assert previous is not None

    with store.write() as transaction:
        upsert_member(
            transaction,
            program_id=PROGRAM,
            settings=MemberSettings(
                project_id=ADDRESSEE,
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                rules_from=RulesFrom.NAMED,
                wake_command=None,
            ),
            now=LATER,
        )
        kept = get_message(transaction, "open-one")
        live = transaction.execute(
            "SELECT count(*) FROM messages WHERE state IN ('open', 'accepted')"
        ).fetchone()

    assert kept == previous
    assert kept is not None
    assert kept.state is RequestState.CANCELLED
    assert live == (0,)
