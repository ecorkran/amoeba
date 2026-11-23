"""``inbox``: the held requests, deliveries since a number, and no writes (slice 240,
D7)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT
from store.message_support import count

from amoeba.operations.deps import Deps
from amoeba.operations.message_models import InboxOutcome
from amoeba.operations.message_results import InboxResult, RequestDirection
from amoeba.operations.reject_codes import RejectCode
from amoeba.store.deliveries import highest_assigned_seq
from amoeba.store.message_sweep import sweep
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, RequestState
from operations.message_placed import inbox, reply
from operations.message_support import (
    CONFIG,
    RECIPIENT,
    RECIPIENT_NAME,
    SENDER,
    SENDER_NAME,
    end_request,
    message_cf,
    message_deps,
    open_message_store,
    rejection_rows,
    send_note_as_sender,
    send_request_as_sender,
)
from operations.release_support import SettableClock
from operations.set_up_support import DIRECTORY

TTL = timedelta(hours=CONFIG.request_open_ttl_hours)
RETENTION = timedelta(days=CONFIG.prune_after_days)


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
    """A session in no member: the addressee is named with ``member``."""
    return message_deps(tmp_path, clock, message_cf(OUTSIDE_ANY_PROJECT))


def _as_sender(store: Store, deps: Deps, **fields: Any) -> InboxResult:
    return inbox(store, fields, directory=DIRECTORY, deps=deps)


def _as_addressee(store: Store, deps: Deps, **fields: Any) -> InboxResult:
    return inbox(
        store, {"member": RECIPIENT_NAME, **fields}, directory=DIRECTORY, deps=deps
    )


def _reply(
    store: Store, deps: Deps, request_id: str, action: str, **fields: Any
) -> None:
    document = {"id": request_id, "action": action, "member": RECIPIENT_NAME, **fields}
    reply(store, CONFIG, document, directory=DIRECTORY, deps=deps)


def _ids(result: InboxResult) -> list[str]:
    return [view.id for view in result.requests]


def test_without_since_every_held_request_is_listed_with_no_deliveries(
    store: Store, sender_deps: Deps, outside_deps: Deps, clock: SettableClock
) -> None:
    send_request_as_sender(store, sender_deps, "live")
    clock.now += timedelta(minutes=1)
    send_request_as_sender(store, sender_deps, "finished")
    end_request(store, "finished", RequestState.DONE, sender_deps)

    result = _as_addressee(store, outside_deps)

    assert result.outcome is InboxOutcome.LISTED
    assert result.member == RECIPIENT
    assert result.since is None
    assert _ids(result) == ["live", "finished"]
    assert [view.state for view in result.requests] == [
        RequestState.OPEN,
        RequestState.DONE,
    ]
    assert result.deliveries == ()
    assert result.notice


def test_without_since_a_pruned_request_is_gone(
    store: Store, sender_deps: Deps, outside_deps: Deps, clock: SettableClock
) -> None:
    send_request_as_sender(store, sender_deps, "old")
    end_request(store, "old", RequestState.DONE, sender_deps)
    clock.now += RETENTION + timedelta(days=1)
    send_request_as_sender(store, sender_deps, "fresh")

    result = _as_addressee(store, outside_deps)

    assert _ids(result) == ["fresh"]


def test_a_request_is_shown_to_its_sender_and_its_addressee_with_a_direction(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")

    sent = _as_sender(store, sender_deps)
    received = _as_addressee(store, outside_deps)

    assert [view.direction for view in sent.requests] == [RequestDirection.SENT]
    assert [view.direction for view in received.requests] == [RequestDirection.RECEIVED]


def test_since_returns_only_later_deliveries_in_order(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "first")
    before = _as_addressee(store, outside_deps)
    assert before.as_of_seq is not None
    send_request_as_sender(store, sender_deps, "second")
    send_request_as_sender(store, sender_deps, "third")

    result = _as_addressee(store, outside_deps, since=before.as_of_seq)

    assert [(item.message_id, item.event) for item in result.deliveries] == [
        ("second", DeliveryEvent.SENT),
        ("third", DeliveryEvent.SENT),
    ]
    assert result.deliveries[0].seq < result.deliveries[1].seq
    assert _ids(result) == ["second", "third"]
    assert result.since == before.as_of_seq


def test_a_request_changed_twice_is_once_in_requests_and_twice_in_deliveries(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    _reply(store, outside_deps, "ask", "accept")
    _reply(store, outside_deps, "ask", "done", text="finished")

    result = _as_sender(store, sender_deps, since=0)

    assert [(item.message_id, item.event) for item in result.deliveries] == [
        ("ask", DeliveryEvent.ACCEPTED),
        ("ask", DeliveryEvent.DONE),
    ]
    assert _ids(result) == ["ask"]
    assert result.requests[0].state is RequestState.DONE


def test_an_unswept_expiry_shows_at_once_and_its_delivery_follows_a_sweep(
    store: Store, sender_deps: Deps, clock: SettableClock
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    start = _as_sender(store, sender_deps)
    assert start.as_of_seq is not None
    clock.now += TTL

    unswept = _as_sender(store, sender_deps, since=start.as_of_seq)

    assert _ids(unswept) == ["ask"]
    assert unswept.requests[0].state is RequestState.EXPIRED
    assert unswept.deliveries == ()
    with store.write() as transaction:
        sweep(transaction, clock.now, CONFIG.prune_after_days)

    swept = _as_sender(store, sender_deps, since=start.as_of_seq)

    assert _ids(swept) == ["ask"]
    assert [(item.message_id, item.event) for item in swept.deliveries] == [
        ("ask", DeliveryEvent.EXPIRED)
    ]


def test_as_of_seq_does_not_fall_when_deliveries_are_pruned(
    store: Store, sender_deps: Deps, clock: SettableClock
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    end_request(store, "ask", RequestState.DONE, sender_deps)
    before = _as_sender(store, sender_deps).as_of_seq
    clock.now += RETENTION + timedelta(days=1)
    with store.write() as transaction:
        sweep(transaction, clock.now, CONFIG.prune_after_days)
        assert count(transaction, "deliveries") == 0

    after = _as_sender(store, sender_deps)

    assert before is not None and before > 0
    assert after.as_of_seq == before
    assert after.requests == ()


def test_since_beyond_the_last_delivery_is_beyond_last_record(
    store: Store, sender_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    with store.read() as transaction:
        last = highest_assigned_seq(transaction)

    result = _as_sender(store, sender_deps, since=last + 1)

    assert result.outcome is InboxOutcome.REJECTED
    assert result.rejection is RejectCode.BEYOND_LAST_RECORD
    assert "without since" in result.problems[0]
    assert str(last) in result.problems[0]
    assert (result.requests, result.deliveries) == ((), ())
    assert _as_sender(store, sender_deps, since=last).outcome is InboxOutcome.LISTED


def test_two_readers_with_different_since_each_see_every_delivery_after_their_own(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "one")
    send_request_as_sender(store, sender_deps, "two")
    send_request_as_sender(store, sender_deps, "three")

    early = _as_addressee(store, outside_deps, since=0)
    late = _as_addressee(store, outside_deps, since=early.deliveries[1].seq)
    early_again = _as_addressee(store, outside_deps, since=0)

    assert [item.message_id for item in early.deliveries] == ["one", "two", "three"]
    assert [item.message_id for item in late.deliveries] == ["three"]
    assert early_again == early


def test_inbox_never_writes(store: Store, sender_deps: Deps, tmp_path: Path) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    tables = ("messages", "deliveries", "message_rejections")
    with store.read() as transaction:
        before_rows = [count(transaction, table) for table in tables]
    with closing(sqlite3.connect(store.path)) as observer:
        before = observer.execute("PRAGMA data_version").fetchone()[0]

        _as_sender(store, sender_deps)
        _as_sender(store, sender_deps, since=0)
        _as_sender(store, sender_deps, since=99)

        after = observer.execute("PRAGMA data_version").fetchone()[0]
    with store.read() as transaction:
        assert [count(transaction, table) for table in tables] == before_rows
    assert after == before


@pytest.mark.parametrize("since", [-1, "3", 1.5])
def test_a_malformed_document_is_rejected_and_not_recorded(
    store: Store, sender_deps: Deps, since: object
) -> None:
    result = _as_sender(store, sender_deps, since=since)

    assert result.rejection is RejectCode.MALFORMED
    assert "since" in result.problems[0]
    assert rejection_rows(store) == []


def test_a_member_mismatch_is_rejected_and_not_recorded(
    store: Store, sender_deps: Deps
) -> None:
    result = _as_sender(store, sender_deps, member=RECIPIENT_NAME)

    assert result.rejection is RejectCode.MEMBER_MISMATCH
    assert rejection_rows(store) == []


def test_a_caller_in_no_member_is_rejected(store: Store, outside_deps: Deps) -> None:
    result = _as_sender(store, outside_deps)

    assert result.rejection is RejectCode.NOT_A_MEMBER


def test_the_senders_own_name_resolves_from_its_directory(
    store: Store, sender_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")

    result = _as_sender(store, sender_deps, member=SENDER_NAME)

    assert result.member == SENDER
    assert _ids(result) == ["ask"]


def test_a_note_in_the_store_is_not_listed_among_the_requests(
    store: Store, sender_deps: Deps, outside_deps: Deps
) -> None:
    send_request_as_sender(store, sender_deps, "ask")
    send_note_as_sender(store, sender_deps, "a-note")

    assert _ids(_as_addressee(store, outside_deps)) == ["ask"]
    assert _ids(_as_sender(store, sender_deps)) == ["ask"]
    assert _ids(_as_addressee(store, outside_deps, since=0)) == ["ask"]
    assert "a-note" not in _ids(_as_sender(store, sender_deps, since=0))
