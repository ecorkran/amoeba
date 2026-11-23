"""Wake row reads, writes and prune (slice 244, D3, D9, D10)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from amoeba.store.vocabulary import WakeOutcome
from amoeba.store.wakes import (
    finish_wake,
    get_wake,
    prune_wakes,
    set_command_pid,
    wake_summary,
    wakes_due,
)
from store.message_support import ADDRESSEE, NOW, seed_members
from store.wake_support import (
    HOUR,
    TIMEOUT_SECONDS,
    claim,
    seed_waking_member,
)

TICK = timedelta(microseconds=1)
RETENTION = timedelta(days=30)
PID = 4242


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction)
            seed_waking_member(transaction)
        yield opened


def test_finish_wake_ends_once_and_a_second_call_returns_false(store: Store) -> None:
    with store.write() as transaction:
        claim(transaction, "w1")
        first = finish_wake(
            transaction, "w1", WakeOutcome.EXITED, 3, "detail", NOW + HOUR
        )
        second = finish_wake(transaction, "w1", WakeOutcome.TIMED_OUT, None, None, NOW)
        row = get_wake(transaction, "w1")

    assert (first, second) == (True, False)
    assert row is not None
    assert (row.outcome, row.exit_code, row.detail) == (WakeOutcome.EXITED, 3, "detail")
    assert row.ended_at == NOW + HOUR


def test_finishing_an_unknown_row_returns_false(store: Store) -> None:
    with store.write() as transaction:
        assert not finish_wake(transaction, "nope", WakeOutcome.EXITED, 0, None, NOW)


def test_set_command_pid_is_shown_by_get_wake(store: Store) -> None:
    with store.write() as transaction:
        claim(transaction, "w1")
        set_command_pid(transaction, "w1", PID)
        row = get_wake(transaction, "w1")

    assert row is not None
    assert row.command_pid == PID


def test_set_command_pid_is_recorded_once_and_not_after_the_row_ended(
    store: Store,
) -> None:
    with store.write() as transaction:
        claim(transaction, "w1")
        first = set_command_pid(transaction, "w1", PID)
        second = set_command_pid(transaction, "w1", PID + 1)
        finish_wake(transaction, "w1", WakeOutcome.EXITED, 0, None, NOW)
        claim(transaction, "w2", now=NOW + HOUR)
        finish_wake(transaction, "w2", WakeOutcome.EXITED, 0, None, NOW + HOUR)
        after_end = set_command_pid(transaction, "w2", PID)
        row = get_wake(transaction, "w1")

    assert (first, second, after_end) == (True, False, False)
    assert row is not None
    assert row.command_pid == PID


def test_prune_deletes_an_unended_aged_row_and_keeps_a_young_one(store: Store) -> None:
    with store.write() as transaction:
        claim(transaction, "aged", now=NOW)
        claim(transaction, "young", now=NOW + RETENTION, max_wakes=5)
        removed = prune_wakes(transaction, encode_timestamp(NOW + TICK))
        aged = get_wake(transaction, "aged")
        young = get_wake(transaction, "young")

    assert removed == 1
    assert aged is None
    assert young is not None


def test_wakes_due_is_true_for_an_aged_row_and_false_for_a_young_one(
    store: Store,
) -> None:
    with store.write() as transaction:
        claim(transaction, "w1", now=NOW)
        cutoff_before = encode_timestamp(NOW)
        cutoff_after = encode_timestamp(NOW + TICK)
        young_only = wakes_due(transaction, cutoff_before)
        aged = wakes_due(transaction, cutoff_after)

    assert (young_only, aged) == (False, True)


def test_the_summary_of_a_member_with_no_wakes_is_empty(store: Store) -> None:
    with store.read() as transaction:
        summary = wake_summary(transaction, ADDRESSEE, NOW)

    assert (summary.unended, summary.overdue, summary.used_in_window) == (
        None,
        False,
        0,
    )
    assert summary.newest_ended is None


def test_the_summary_has_the_three_parts_and_a_live_row_is_not_overdue(
    store: Store,
) -> None:
    with store.write() as transaction:
        claim(transaction, "old")
        finish_wake(transaction, "old", WakeOutcome.START_FAILED, None, "x", NOW + TICK)
        claim(transaction, "now", now=NOW + HOUR)
        summary = wake_summary(transaction, ADDRESSEE, NOW + HOUR)

    assert summary.unended is not None
    assert summary.unended.wake_id == "now"
    assert not summary.overdue
    assert summary.used_in_window == 2
    assert summary.newest_ended is not None
    assert summary.newest_ended.wake_id == "old"


def test_an_unended_row_past_its_deadline_is_overdue(store: Store) -> None:
    deadline = NOW + timedelta(seconds=TIMEOUT_SECONDS)
    with store.write() as transaction:
        claim(transaction, "w1")
        before = wake_summary(transaction, ADDRESSEE, deadline - TICK)
        at = wake_summary(transaction, ADDRESSEE, deadline)

    assert not before.overdue
    assert at.overdue
    assert at.unended is not None
    assert at.unended.wake_id == "w1"


def test_the_newest_ended_row_is_the_one_ended_last(store: Store) -> None:
    with store.write() as transaction:
        claim(transaction, "a", now=NOW)
        finish_wake(transaction, "a", WakeOutcome.EXITED, 0, None, NOW + 2 * HOUR)
        claim(transaction, "b", now=NOW + HOUR)
        finish_wake(transaction, "b", WakeOutcome.TIMED_OUT, None, None, NOW + 3 * HOUR)
        summary = wake_summary(transaction, ADDRESSEE, NOW + 4 * HOUR)

    assert summary.newest_ended is not None
    assert summary.newest_ended.wake_id == "b"
