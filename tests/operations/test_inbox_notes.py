"""``inbox`` lists the notes a member has a delivery for (slice 243, D4)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT
from store.message_support import PROGRAM, count

from amoeba.operations.deps import Deps
from amoeba.operations.inbox import inbox
from amoeba.operations.message_results import InboxResult
from amoeba.operations.reject_codes import RejectCode
from amoeba.store.store import Store
from operations.message_support import (
    RECIPIENT_NAME,
    SENDER,
    SENDER_NAME,
    THIRD_NAME,
    message_cf,
    message_deps,
    open_message_store,
    send_note_as_sender,
    send_request_as_sender,
)
from operations.release_support import SettableClock
from operations.set_up_support import DIRECTORY


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    yield from open_message_store(tmp_path)


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def sender_deps(tmp_path: Path, clock: SettableClock) -> Deps:
    return message_deps(tmp_path, clock)


@pytest.fixture
def outside_deps(tmp_path: Path, clock: SettableClock) -> Deps:
    """A session in no member: the reader is named with ``member``."""
    return message_deps(tmp_path, clock, message_cf(OUTSIDE_ANY_PROJECT))


def _read(store: Store, deps: Deps, member_name: str, **fields: Any) -> InboxResult:
    return inbox(
        store, {"member": member_name, **fields}, directory=DIRECTORY, deps=deps
    )


def _note_ids(result: InboxResult) -> list[str]:
    return [note.id for note in result.notes]


def test_a_member_sees_the_notes_it_has_a_delivery_for_with_and_without_since(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_note_as_sender(store, sender_deps, "direct")
    send_note_as_sender(store, sender_deps, "shared", to=None, to_program=PROGRAM)

    for fields in ({}, {"since": 0}):
        result = _read(store, outside_deps, RECIPIENT_NAME, **fields)
        assert _note_ids(result) == ["direct", "shared"]
        assert result.requests == ()


def test_a_member_does_not_see_a_note_it_has_no_delivery_for(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_note_as_sender(store, sender_deps, "direct")

    assert _note_ids(_read(store, outside_deps, THIRD_NAME)) == []
    assert _note_ids(_read(store, outside_deps, THIRD_NAME, since=0)) == []


def test_a_program_notes_sender_does_not_see_it(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_note_as_sender(store, sender_deps, "shared", to=None, to_program=PROGRAM)

    assert _note_ids(_read(store, outside_deps, SENDER_NAME)) == []
    assert _note_ids(_read(store, outside_deps, THIRD_NAME)) == ["shared"]


def test_a_direct_note_to_ones_own_member_shows(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_note_as_sender(store, sender_deps, "to-self", to=SENDER_NAME)

    result = _read(store, outside_deps, SENDER_NAME)

    assert _note_ids(result) == ["to-self"]
    assert result.notes[0].from_member == SENDER == result.member


def test_with_since_the_later_notes_come_once_each_with_their_sent_deliveries(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_note_as_sender(store, sender_deps, "first")
    cursor = _read(store, outside_deps, RECIPIENT_NAME).as_of_seq
    assert cursor is not None
    send_note_as_sender(store, sender_deps, "second")
    send_note_as_sender(store, sender_deps, "third")

    result = _read(store, outside_deps, RECIPIENT_NAME, since=cursor)

    assert _note_ids(result) == ["second", "third"]
    assert [(item.message_id, item.event.value) for item in result.deliveries] == [
        ("second", "sent"),
        ("third", "sent"),
    ]
    assert [item.seq for item in result.deliveries] == sorted(
        item.seq for item in result.deliveries
    )
    assert result.as_of_seq == result.deliveries[-1].seq


def test_a_note_lists_beside_a_request_and_deliveries_cover_both(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    send_note_as_sender(store, sender_deps, "a-note")

    result = _read(store, outside_deps, RECIPIENT_NAME, since=0)

    assert [view.id for view in result.requests] == ["ask"]
    assert _note_ids(result) == ["a-note"]
    assert [item.message_id for item in result.deliveries] == ["ask", "a-note"]


def test_since_above_the_last_record_is_still_beyond_last_record(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_note_as_sender(store, sender_deps, "a-note")

    result = _read(store, outside_deps, RECIPIENT_NAME, since=99)

    assert result.rejection is RejectCode.BEYOND_LAST_RECORD
    assert result.notes == ()


def test_inbox_writes_nothing_with_notes_present(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_note_as_sender(store, sender_deps, "a-note")
    send_note_as_sender(store, sender_deps, "shared", to=None, to_program=PROGRAM)
    tables = ("messages", "deliveries", "message_rejections")
    with store.read() as transaction:
        before_rows = [count(transaction, table) for table in tables]
    with closing(sqlite3.connect(store.path)) as observer:
        before = observer.execute("PRAGMA data_version").fetchone()[0]

        _read(store, outside_deps, RECIPIENT_NAME)
        _read(store, outside_deps, RECIPIENT_NAME, since=0)

        after = observer.execute("PRAGMA data_version").fetchone()[0]
    with store.read() as transaction:
        assert [count(transaction, table) for table in tables] == before_rows
    assert after == before
