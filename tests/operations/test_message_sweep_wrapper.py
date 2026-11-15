"""``sweep_messages``: no write lock on a quiet store, due work swept, a busy store
reported (slice 240, D6)."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import pytest
from store.message_support import delivery_rows, seed_members

from amoeba.operations.message_sweep import sweep_messages
from amoeba.store.messages import get_message
from amoeba.store.store import Store
from amoeba.store.vocabulary import RequestState
from operations.message_support import (
    CONFIG,
    RECIPIENT,
    SENDER,
    THIRD,
    message_deps,
    send_request_as_sender,
)
from operations.release_support import SettableClock

TTL = timedelta(hours=CONFIG.request_open_ttl_hours)
SHORT_BUSY_TIMEOUT_SECONDS = 0.2


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(
        tmp_path / "amoeba.sqlite3", busy_timeout_seconds=SHORT_BUSY_TIMEOUT_SECONDS
    ) as opened:
        with opened.write() as transaction:
            seed_members(transaction, SENDER, RECIPIENT, THIRD)
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
