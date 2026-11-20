"""Removing a member cancels its live requests (slice 240, D10).

Both ``rm`` and ``add``'s remove path reach ``apply_removal``, so both cascade, and the
cascade shares the removal's transaction.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import DEFAULT_WORKTREE
from store.message_support import NOW, delivery_rows, send_request
from user_configs import user_config

from amoeba.operations import set_up_remove
from amoeba.operations.rm import rm
from amoeba.operations.set_up_models import SetUpOutcome
from amoeba.store.messages import get_message
from amoeba.store.notes import NewNote, insert_note
from amoeba.store.programs import get_member_any
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import MEMBER_REMOVED_REASON, RequestState
from operations.set_up_support import DIRECTORY, FakeCf, run_set_up

PROVIDER = "provider-id"
CONSUMER = "consumer-id"
PROJECTS = [(PROVIDER, "provider"), (CONSUMER, "consumer")]
NOTE_IDS = ("to-it", "from-it")
RULES = {"rules_paths": ["CLAUDE.md"]}
REMOVE_CONSUMER = {"program": "demo", "remove": {"members": ["consumer"]}}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        result = run_set_up(
            opened,
            {
                "program": "demo",
                "members": [
                    {"project": "provider", **RULES},
                    {"project": "consumer", **RULES},
                ],
            },
            projects=PROJECTS,
        )
        assert result.outcome is SetUpOutcome.APPLIED
        with opened.write() as transaction:
            send_request(transaction, "sent", from_member=CONSUMER, to_member=PROVIDER)
            send_request(
                transaction, "received", from_member=PROVIDER, to_member=CONSUMER
            )
        yield opened


def _remove_by_rm(store: Store) -> None:
    result = rm(
        store,
        user_config(),
        {"members": ["consumer"]},
        directory=DIRECTORY,
        run=FakeCf(directory_fixture=DEFAULT_WORKTREE, projects=PROJECTS),
    )
    assert result.outcome is SetUpOutcome.APPLIED


def _remove_by_add(store: Store) -> None:
    result = run_set_up(store, REMOVE_CONSUMER, projects=PROJECTS)
    assert result.outcome is SetUpOutcome.APPLIED


def _request(store: Store, request_id: str) -> Any:
    with store.read() as transaction:
        return get_message(transaction, request_id)


@pytest.mark.parametrize("remove", [_remove_by_rm, _remove_by_add])
def test_removing_a_member_cancels_its_sent_and_received_requests(
    store: Store, remove: Any
) -> None:
    remove(store)

    for request_id in ("sent", "received"):
        row = _request(store, request_id)
        assert row.state is RequestState.CANCELLED
        assert row.reason == MEMBER_REMOVED_REASON
    with store.read() as transaction:
        # The surviving provider hears of each; the removed consumer hears of none.
        assert sorted(
            (row[1], row[2], row[3]) for row in delivery_rows(transaction)
        ) == [
            (PROVIDER, "received", "cancelled"),
            (PROVIDER, "sent", "cancelled"),
        ]


def test_a_finished_request_is_left_alone(store: Store) -> None:
    with store.write() as transaction:
        send_request(transaction, "old", from_member=CONSUMER, to_member=PROVIDER)
        transaction.execute(
            "UPDATE messages SET state = 'done' WHERE message_id = 'old'"
        )

    _remove_by_add(store)

    assert _request(store, "old").state is RequestState.DONE
    assert _request(store, "old").reason is None


def test_a_request_between_other_members_is_untouched(store: Store) -> None:
    with store.write() as transaction:
        send_request(transaction, "elsewhere", from_member=PROVIDER, to_member=PROVIDER)

    _remove_by_add(store)

    assert _request(store, "elsewhere").state is RequestState.OPEN


@pytest.mark.parametrize("remove", [_remove_by_rm, _remove_by_add])
def test_the_whole_removal_rolls_back_if_the_cascade_fails(
    store: Store, monkeypatch: pytest.MonkeyPatch, remove: Any
) -> None:
    def failing(*_arguments: object) -> None:
        raise RuntimeError("the cascade failed")

    monkeypatch.setattr(set_up_remove, "cancel_member_requests", failing)

    with pytest.raises(RuntimeError, match="the cascade failed"):
        remove(store)

    with store.read() as transaction:
        member = get_member_any(transaction, CONSUMER)
    assert member is not None and member.removed_at is None
    assert _request(store, "sent").state is RequestState.OPEN
    with store.read() as transaction:
        assert delivery_rows(transaction) == []


def _note_deliveries(transaction: Transaction) -> list[tuple[int, str, str, str]]:
    return [row for row in delivery_rows(transaction) if row[2] in NOTE_IDS]


@pytest.mark.parametrize("remove", [_remove_by_rm, _remove_by_add])
def test_removing_a_member_leaves_notes_to_and_from_it_and_their_deliveries(
    store: Store, remove: Any
) -> None:
    with store.write() as transaction:
        to_removed = NewNote("to-it", PROVIDER, CONSUMER, None, "s", "b")
        from_removed = NewNote("from-it", CONSUMER, PROVIDER, None, "s", "b")
        insert_note(transaction, to_removed, [CONSUMER], NOW)
        insert_note(transaction, from_removed, [PROVIDER], NOW)
        before = _note_deliveries(transaction)
    assert len(before) == 2

    remove(store)

    for note_id in NOTE_IDS:
        row = _request(store, note_id)
        assert row is not None and row.state is None
    with store.read() as transaction:
        assert _note_deliveries(transaction) == before
