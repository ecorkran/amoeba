"""``wake_due``: one test per rule and per case of D8 (slice 262)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.machines import ActingMachine, invite_machine, the_owner
from amoeba.store.models import Session
from amoeba.store.row_values import encode_timestamp
from amoeba.store.sessions import upsert_session
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import WakeOutcome
from amoeba.store.wakes import (
    WakeScope,
    claim_wake,
    finish_wake,
    set_command_pid,
    set_wake_mark,
    wake_due,
)
from amoeba.wire.times import DOOR_VERSION
from store.message_support import ADDRESSEE, NOW, SENDER, seed_members
from store.seed import mark_wake_wanted
from store.wake_support import (
    LIMITS,
    TIMEOUT_SECONDS,
    seed_waking_member,
)

SECOND = timedelta(seconds=1)
AFTER_DEADLINE = timedelta(seconds=TIMEOUT_SECONDS + 1)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, SENDER)
            seed_waking_member(transaction)
        yield opened


def _due(transaction: Transaction, now_offset: timedelta = timedelta(0)) -> bool:
    return wake_due(transaction, ADDRESSEE, NOW + now_offset, LIMITS)


def _claim(transaction: Transaction, wake_id: str, at: timedelta) -> None:
    claimed = claim_wake(
        transaction, ADDRESSEE, NOW + at, LIMITS, wake_id, f"/logs/{wake_id}"
    )
    assert claimed is not None


def test_no_mark_is_not_due(store: Store) -> None:
    with store.read() as transaction:
        assert not _due(transaction)


def test_a_mark_and_no_wake_since_is_due(store: Store) -> None:
    with store.write() as transaction:
        mark_wake_wanted(transaction, ADDRESSEE, NOW)

        assert _due(transaction)


def test_a_mark_on_a_request_that_is_not_open_or_has_expired_is_not_due(
    store: Store,
) -> None:
    with store.write() as transaction:
        mark_wake_wanted(transaction, ADDRESSEE, NOW)
        transaction.execute(
            "UPDATE messages SET expires_at = ?", (encode_timestamp(NOW + 30 * SECOND),)
        )

        assert wake_due(transaction, ADDRESSEE, NOW + 29 * SECOND, LIMITS)
        assert not wake_due(transaction, ADDRESSEE, NOW + 30 * SECOND, LIMITS)

        transaction.execute("UPDATE messages SET state = 'accepted'")

        assert not wake_due(transaction, ADDRESSEE, NOW, LIMITS)


def test_a_wake_claimed_at_the_marks_own_time_is_that_marks_wake(store: Store) -> None:
    with store.write() as transaction:
        mark_wake_wanted(transaction, ADDRESSEE, NOW)
        _claim(transaction, "w1", timedelta(0))
        finish_wake(transaction, "w1", WakeOutcome.EXITED, 0, None, NOW + SECOND)

        assert not _due(transaction, SECOND)


def test_a_wake_claimed_before_the_mark_does_not_answer_it(store: Store) -> None:
    with store.write() as transaction:
        mark_wake_wanted(transaction, ADDRESSEE, NOW)
        _claim(transaction, "w1", timedelta(0))
        finish_wake(transaction, "w1", WakeOutcome.EXITED, 0, None, NOW + SECOND)
        mark_wake_wanted(transaction, ADDRESSEE, NOW + 2 * SECOND)

        assert _due(transaction, 3 * SECOND)


def test_a_row_with_a_pid_past_its_deadline_is_its_own_marks_wake_only(
    store: Store,
) -> None:
    with store.write() as transaction:
        mark_wake_wanted(transaction, ADDRESSEE, NOW)
        _claim(transaction, "w1", timedelta(0))
        assert set_command_pid(transaction, "w1", 4242)
        later = AFTER_DEADLINE

        # Unended and past its deadline, but it ran: still the first mark's wake.
        assert not _due(transaction, later)
        mark_wake_wanted(transaction, ADDRESSEE, NOW + later)

        assert _due(transaction, later)


def test_an_unended_row_with_no_pid_past_its_deadline_lets_the_mark_be_due_again(
    store: Store,
) -> None:
    with store.write() as transaction:
        mark_wake_wanted(transaction, ADDRESSEE, NOW)
        _claim(transaction, "w1", timedelta(0))

        assert not _due(transaction, AFTER_DEADLINE - 2 * SECOND)  # still live
        assert _due(transaction, AFTER_DEADLINE)


def test_a_live_session_on_another_machine_is_not_due(store: Store) -> None:
    with store.write() as transaction:
        invite_machine(transaction, "beta", "f" * 64, NOW)
        beta = int(
            transaction.execute(
                "SELECT machine_id FROM machines WHERE name = 'beta'"
            ).fetchone()[0]
        )
        owner = the_owner(transaction)
        mark_wake_wanted(transaction, ADDRESSEE, NOW)
        assert _due(transaction)
    local = ActingMachine(_local_machine_id(store), owner)
    store.act_as(ActingMachine(beta, owner))
    with store.write() as transaction:
        upsert_session(
            transaction,
            Session(
                "on-beta",
                ADDRESSEE,
                "claude",
                "/beta",
                NOW,
                NOW,
                NOW,
                "9.9.9",
                DOOR_VERSION,
            ),
        )
    store.act_as(local)

    with store.read() as transaction:
        assert not _due(transaction)
        assert not wake_due(transaction, ADDRESSEE, NOW, LIMITS, WakeScope.ALL_MACHINES)


def _local_machine_id(store: Store) -> int:
    with store.read() as transaction:
        row = transaction.execute(
            "SELECT machine_id FROM machines WHERE name = 'local'"
        ).fetchone()
    assert row is not None
    return int(row[0])


def test_a_start_failed_wake_is_not_due_again_for_that_mark(store: Store) -> None:
    with store.write() as transaction:
        mark_wake_wanted(transaction, ADDRESSEE, NOW)
        _claim(transaction, "w1", timedelta(0))
        finish_wake(transaction, "w1", WakeOutcome.START_FAILED, None, "no", NOW)

        assert not _due(transaction, SECOND)
        assert not _due(transaction, AFTER_DEADLINE * 10)


def test_sent_again_once_the_session_is_stale_is_a_new_mark_and_due(
    store: Store,
) -> None:
    with store.write() as transaction:
        upsert_session(
            transaction,
            Session(
                "live",
                ADDRESSEE,
                "claude",
                "/w",
                NOW,
                NOW,
                NOW,
                "9.9.9",
                DOOR_VERSION,
            ),
        )
        request = mark_wake_wanted(transaction, ADDRESSEE, NOW)
        # The first send saw a live session: it set no mark.
        assert not set_wake_mark(transaction, request, ADDRESSEE, NOW, LIMITS)
        transaction.execute("UPDATE messages SET wake_wanted_at = NULL")
        stale = timedelta(seconds=LIMITS.session_stale_seconds + 1)
        assert not wake_due(transaction, ADDRESSEE, NOW + stale, LIMITS)

        # Sent again unchanged after the session went stale: a new mark.
        assert set_wake_mark(transaction, request, ADDRESSEE, NOW + stale, LIMITS)

        assert wake_due(transaction, ADDRESSEE, NOW + stale, LIMITS)
