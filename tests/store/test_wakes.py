"""`claim_wake` and `can_wake`: the checks, their order and the row (244, D2, D3)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.models import Session
from amoeba.store.programs import remove_member
from amoeba.store.sessions import upsert_session
from amoeba.store.store import Store
from amoeba.store.vocabulary import WakeOutcome
from amoeba.store.wakes import (
    NO_CHECKOUT_DETAIL,
    WAKE_WINDOW,
    can_wake,
    finish_wake,
    get_wake,
)
from store.message_support import ADDRESSEE, NOW, SENDER, seed_members
from store.seed import insert_member
from store.wake_support import (
    COMMAND,
    DIRECTORY,
    HOUR,
    LIMITS,
    LOG_DIRECTORY,
    MAX_WAKES,
    TIMEOUT_SECONDS,
    claim,
    confirmed_session,
)

TICK = timedelta(microseconds=1)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    """A store holding the sender and an addressee with a wake command."""
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, SENDER)
            insert_member(
                transaction,
                project_id=ADDRESSEE,
                program_id="demo",
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=NOW,
                updated_at=NOW,
                wake_command=COMMAND,
            )
        yield opened


def test_a_removed_member_is_not_claimed(store: Store) -> None:
    with store.write() as transaction:
        remove_member(transaction, ADDRESSEE, NOW)
        assert claim(transaction, "w1") is None
        assert not can_wake(transaction, ADDRESSEE, NOW, LIMITS)


def test_an_unknown_member_is_not_claimed(store: Store) -> None:
    with store.write() as transaction:
        assert claim(transaction, "w1", member_id="nobody") is None


def test_a_member_with_no_command_is_not_claimed(store: Store) -> None:
    with store.write() as transaction:
        transaction.execute("UPDATE members SET wake_command = NULL")
        assert claim(transaction, "w1") is None
        assert not can_wake(transaction, ADDRESSEE, NOW, LIMITS)


def test_a_push_confirmed_live_session_blocks_the_claim(store: Store) -> None:
    with store.write() as transaction:
        confirmed_session(transaction)
        assert claim(transaction, "w1") is None
        assert not can_wake(transaction, ADDRESSEE, NOW, LIMITS)


def test_a_session_that_is_not_push_confirmed_does_not_block(store: Store) -> None:
    with store.write() as transaction:
        upsert_session(
            transaction,
            Session(
                session_id="s1",
                member_id=ADDRESSEE,
                client="claude-code",
                directory="/work",
                started_at=NOW,
                heartbeat_at=NOW,
                push_confirmed_at=None,
            ),
        )
        assert claim(transaction, "w1") is not None


def test_a_live_wake_blocks_the_claim(store: Store) -> None:
    with store.write() as transaction:
        assert claim(transaction, "w1") is not None
        assert claim(transaction, "w2", now=NOW + TICK) is None
        assert not can_wake(transaction, ADDRESSEE, NOW + TICK, LIMITS)


def test_the_limit_blocks_the_claim_and_writes_no_row(store: Store) -> None:
    with store.write() as transaction:
        for index in range(MAX_WAKES):
            at = NOW + index * timedelta(hours=1)
            wake = claim(transaction, f"w{index}", now=at)
            assert wake is not None
            finish_wake(transaction, wake.wake_id, WakeOutcome.EXITED, 0, None, at)
        later = NOW + MAX_WAKES * HOUR
        assert claim(transaction, "over", now=later) is None
        assert get_wake(transaction, "over") is None


def test_the_checks_run_in_the_designed_order(store: Store) -> None:
    """With every check failing, removing the causes one by one in reverse order
    makes each next check the one that stops the claim."""
    with store.write() as transaction:
        first = claim(transaction, "used", max_wakes=1)
        assert first is not None
        confirmed_session(transaction, now=NOW + TICK)
        at = NOW + TICK
        assert claim(transaction, "w", now=at, max_wakes=1) is None  # session first
        transaction.execute("DELETE FROM sessions")
        assert claim(transaction, "w", now=at, max_wakes=1) is None  # live wake
        finish_wake(transaction, "used", WakeOutcome.EXITED, 0, None, at)
        assert claim(transaction, "w", now=at, max_wakes=1) is None  # the limit
        assert claim(transaction, "w", now=at, max_wakes=2) is not None


def test_a_claimed_row_has_the_designed_fields(store: Store) -> None:
    with store.write() as transaction:
        wake = claim(transaction, "w1")

    assert wake is not None
    assert wake.wake_id == "w1"
    assert wake.member_id == ADDRESSEE
    assert wake.directory == DIRECTORY
    assert wake.command == COMMAND
    assert wake.started_at == NOW
    assert wake.deadline_at == NOW + timedelta(seconds=TIMEOUT_SECONDS)
    assert wake.log_stem == f"{LOG_DIRECTORY}/w1"
    assert (wake.command_pid, wake.ended_at, wake.outcome) == (None, None, None)
    assert (wake.exit_code, wake.detail) == (None, None)


def test_a_row_past_its_deadline_is_not_live(store: Store) -> None:
    deadline = NOW + timedelta(seconds=TIMEOUT_SECONDS)
    with store.write() as transaction:
        assert claim(transaction, "w1") is not None
        assert claim(transaction, "w2", now=deadline - TICK) is None
        # At the deadline itself the wake no longer counts as live.
        assert claim(transaction, "w2", now=deadline) is not None


def test_a_row_ended_earlier_still_counts_toward_the_limit(store: Store) -> None:
    with store.write() as transaction:
        for index in range(MAX_WAKES):
            at = NOW + index * HOUR
            assert claim(transaction, f"w{index}", now=at) is not None
            finish_wake(transaction, f"w{index}", WakeOutcome.TIMED_OUT, None, None, at)
        assert claim(transaction, "over", now=NOW + MAX_WAKES * HOUR) is None


def test_the_limit_counts_start_failed_rows(store: Store) -> None:
    with store.write() as transaction:
        for index in range(MAX_WAKES):
            at = NOW + index * HOUR
            assert claim(transaction, f"w{index}", now=at, directory=None) is None
        assert claim(transaction, "over", now=NOW + MAX_WAKES * HOUR) is None
        assert get_wake(transaction, "over") is None


def test_a_row_exactly_a_day_old_no_longer_counts(store: Store) -> None:
    with store.write() as transaction:
        assert claim(transaction, "old", max_wakes=1) is not None
        finish_wake(transaction, "old", WakeOutcome.EXITED, 0, None, NOW + HOUR)
        almost = NOW + WAKE_WINDOW - TICK
        assert claim(transaction, "w", now=almost, max_wakes=1) is None
        assert claim(transaction, "w", now=NOW + WAKE_WINDOW, max_wakes=1) is not None


def test_a_null_directory_inserts_an_ended_start_failed_row(store: Store) -> None:
    with store.write() as transaction:
        result = claim(transaction, "w1", directory=None)
        row = get_wake(transaction, "w1")

    assert result is None
    assert row is not None
    assert row.outcome is WakeOutcome.START_FAILED
    assert row.ended_at == NOW
    assert row.detail == NO_CHECKOUT_DETAIL
    assert (row.directory, row.log_stem, row.command) == (None, None, COMMAND)


def test_can_wake_agrees_with_claim_wake_over_the_same_fixtures(store: Store) -> None:
    cases: list[bool] = []
    with store.write() as transaction:
        cases.append(can_wake(transaction, ADDRESSEE, NOW, LIMITS))
        claimed = claim(transaction, "w1")
        cases.append(claimed is not None)
        cases.append(can_wake(transaction, ADDRESSEE, NOW, LIMITS))
        cases.append(claim(transaction, "w2") is not None)
        confirmed_session(transaction)
        cases.append(can_wake(transaction, ADDRESSEE, NOW, LIMITS))

    assert cases == [True, True, False, False, False]


def test_a_later_edit_of_the_command_leaves_the_stored_row_unchanged(
    store: Store,
) -> None:
    with store.write() as transaction:
        claim(transaction, "w1")
        transaction.execute("UPDATE members SET wake_command = 'other'")
        row = get_wake(transaction, "w1")

    assert row is not None
    assert row.command == COMMAND
