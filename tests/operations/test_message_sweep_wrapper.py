"""``sweep_messages``: no write lock on a quiet store, due work swept, a busy store
reported (slice 240, D6)."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from store.message_support import count, delivery_rows
from store.seed import mark_wake_wanted
from store.wake_support import give_checkout_command
from store_open import open_local_store

from amoeba.operations.message_sweep import sweep_messages
from amoeba.store.messages import get_message
from amoeba.store.notes import NewNote, insert_note
from amoeba.store.store import Store
from amoeba.store.vocabulary import RequestState
from amoeba.store.wakes import WakeLimits, claim_wake
from operations.message_support import (
    CONFIG,
    RECIPIENT,
    SENDER,
    message_deps,
    seed_message_members,
    send_request_as_sender,
)
from operations.release_support import SettableClock

TTL = timedelta(hours=CONFIG.request_open_ttl_hours)
SHORT_BUSY_TIMEOUT_SECONDS = 0.2


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(
        tmp_path / "amoeba.sqlite3", busy_timeout_seconds=SHORT_BUSY_TIMEOUT_SECONDS
    ) as opened:
        with opened.write() as transaction:
            seed_message_members(transaction)
        yield opened


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


def _hold_write_lock(store: Store) -> sqlite3.Connection:
    holder = sqlite3.connect(store.path, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    return holder


def test_a_quiet_store_is_swept_without_taking_the_write_lock(
    store: Store, clock: SettableClock
) -> None:
    with closing(_hold_write_lock(store)):
        assert sweep_messages(store, CONFIG, clock.now) is None


def test_due_work_is_swept(store: Store, tmp_path: Path, clock: SettableClock) -> None:
    send_request_as_sender(store, message_deps(tmp_path, clock), "ask")
    clock.now += TTL

    assert sweep_messages(store, CONFIG, clock.now) is None

    with store.read() as transaction:
        request = get_message(transaction, "ask")
        assert request is not None and request.state is RequestState.EXPIRED
        assert [row[3] for row in delivery_rows(transaction)] == [
            "sent",
            "expired",
            "expired",
        ]


def test_a_second_sweep_with_nothing_due_writes_nothing(
    store: Store, tmp_path: Path, clock: SettableClock
) -> None:
    send_request_as_sender(store, message_deps(tmp_path, clock), "ask")
    clock.now += TTL
    sweep_messages(store, CONFIG, clock.now)
    with store.read() as transaction:
        before = delivery_rows(transaction)

    with closing(_hold_write_lock(store)):
        assert sweep_messages(store, CONFIG, clock.now) is None

    with store.read() as transaction:
        assert delivery_rows(transaction) == before


def test_a_held_store_returns_the_problem_text_and_the_call_returns(
    store: Store,
    tmp_path: Path,
    clock: SettableClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    send_request_as_sender(store, message_deps(tmp_path, clock), "ask")
    clock.now += TTL

    with closing(_hold_write_lock(store)), caplog.at_level(logging.ERROR):
        problem = sweep_messages(store, CONFIG, clock.now)

    assert problem is not None
    assert "message sweep did not run" in problem
    assert "could not take the store lock" in caplog.text
    with store.read() as transaction:
        request = get_message(transaction, "ask")
        assert request is not None and request.state is RequestState.OPEN
    assert sweep_messages(store, CONFIG, clock.now) is None
    with store.read() as transaction:
        request = get_message(transaction, "ask")
        assert request is not None and request.state is RequestState.EXPIRED


def _write_note(store: Store, when: datetime) -> None:
    note = NewNote("a-note", SENDER, RECIPIENT, None, "subject", "body")
    with store.write() as transaction:
        insert_note(transaction, note, [RECIPIENT], when)


def _note_count(store: Store) -> int:
    with store.read() as transaction:
        return count(transaction, "messages")


def test_a_store_holding_only_an_aged_note_is_swept_with_a_write(
    store: Store, clock: SettableClock
) -> None:
    _write_note(store, clock.now)
    clock.now += timedelta(days=CONFIG.prune_after_days + 1)

    assert sweep_messages(store, CONFIG, clock.now) is None

    assert _note_count(store) == 0


def test_a_store_holding_only_a_young_note_opens_no_write_transaction(
    store: Store, clock: SettableClock
) -> None:
    _write_note(store, clock.now)
    clock.now += timedelta(days=CONFIG.prune_after_days - 1)

    with closing(_hold_write_lock(store)):
        assert sweep_messages(store, CONFIG, clock.now) is None

    assert _note_count(store) == 1


def test_the_expire_step_never_expires_a_note(
    store: Store, clock: SettableClock
) -> None:
    _write_note(store, clock.now)
    clock.now += TTL + timedelta(hours=1)

    assert sweep_messages(store, CONFIG, clock.now) is None

    with store.read() as transaction:
        note = get_message(transaction, "a-note")
        assert note is not None and note.state is None
        assert [row[3] for row in delivery_rows(transaction)] == ["sent"]


def _claim_wake(store: Store, when: datetime) -> None:
    with store.write() as transaction:
        give_checkout_command(transaction, RECIPIENT, "wake-agent", "/work/checkout")
        mark_wake_wanted(transaction, RECIPIENT, when)
        claimed = claim_wake(
            transaction,
            RECIPIENT,
            when,
            WakeLimits(timeout_seconds=600, max_per_day=3, session_stale_seconds=90),
            "a-wake",
            "/work/logs/a-wake",
        )
        assert claimed is not None


def _wake_count(store: Store) -> int:
    with store.read() as transaction:
        return count(transaction, "wakes")


def test_a_store_holding_only_an_aged_wake_row_is_swept_with_a_write(
    store: Store, clock: SettableClock
) -> None:
    _claim_wake(store, clock.now)
    clock.now += timedelta(days=CONFIG.prune_after_days + 1)

    assert sweep_messages(store, CONFIG, clock.now) is None

    assert _wake_count(store) == 0


def test_a_young_wake_row_opens_no_write_transaction(
    store: Store, clock: SettableClock
) -> None:
    _claim_wake(store, clock.now)

    with closing(_hold_write_lock(store)):
        assert sweep_messages(store, CONFIG, clock.now) is None

    assert _wake_count(store) == 1
