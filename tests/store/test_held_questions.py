"""Held-question store functions (slice 242, D2, D3, 3.2)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.answering.values import DeclineReason
from amoeba.store.held_questions import (
    HeldQuestion,
    claim_held,
    held_rows,
    insert_held,
    mark_start_attempted,
    settle_held_waiting,
)
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.question_closing import dismiss_question
from amoeba.store.questions import add_pm_answer, get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import QuestionState
from store.question_support import (
    HELD_REQUEST_ID,
    KEY,
    MEMBER_ID,
    NOW,
    PASSAGE,
    claimed_question,
    insert_held_row,
    seed_members,
    waiting_question,
)

LATER = NOW + timedelta(hours=2)
NEW_RUN = "amoeba-20261110T130000Z-cccccccccccc"
SECOND = QuestionKey("run-2", "2026-11-10T12:00:00+00:00")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def _row(store: Store, key: QuestionKey = KEY) -> QuestionRecord:
    with store.read() as transaction:
        row = get_question(transaction, key)
    assert row is not None
    return row


def _held(store: Store, key: QuestionKey = KEY) -> None:
    with store.write() as transaction:
        insert_held_row(transaction, key)


def _claim(store: Store, key: QuestionKey = KEY) -> bool:
    with store.write() as transaction:
        return claim_held(
            transaction,
            key,
            answering_run_id=NEW_RUN,
            passages=(PASSAGE,),
            slice_label="242 hold-and-release",
            source_commit="def456",
            now=LATER,
        )


def _settle(store: Store, key: QuestionKey = KEY) -> bool:
    with store.write() as transaction:
        return settle_held_waiting(
            transaction,
            key,
            reason=DeclineReason.REQUEST_DECLINED,
            detail="not now",
            now=LATER,
        )


def test_insert_stores_the_request_id_and_a_repeat_loses(store: Store) -> None:
    held = HeldQuestion(KEY, MEMBER_ID, "q", "/work/a")
    with store.write() as transaction:
        assert insert_held(transaction, held, HELD_REQUEST_ID, NOW)
        assert not insert_held(transaction, held, "another", LATER)

    row = _row(store)
    assert row.state is QuestionState.WAITING_ON_REQUEST
    assert row.request_id == HELD_REQUEST_ID
    assert row.claimed_at == row.updated_at == NOW


def test_claim_moves_the_row_to_claimed_and_resets_its_times(store: Store) -> None:
    _held(store)

    assert _claim(store)

    row = _row(store)
    assert row.state is QuestionState.CLAIMED
    assert row.answering_run_id == NEW_RUN
    assert row.passages == (PASSAGE,)
    assert row.slice_label == "242 hold-and-release"
    assert row.source_commit == "def456"
    assert row.claimed_at == row.updated_at == LATER
    assert row.request_id == HELD_REQUEST_ID


def test_claim_refuses_a_row_that_is_not_held(store: Store) -> None:
    missing = QuestionKey("run-missing", KEY.paused_at)
    answered = QuestionKey("run-answered", KEY.paused_at)
    closed = QuestionKey("run-closed", KEY.paused_at)
    with store.write() as transaction:
        insert_question(transaction, claimed_question(), now=NOW)
        insert_question(transaction, waiting_question(answered), now=NOW)
        add_pm_answer(transaction, answered, "yes", now=NOW, via=None)
        insert_held_row(transaction, closed)
    with store.write() as transaction:
        current = get_question(transaction, closed)
        assert current is not None
        assert dismiss_question(transaction, current, "gone", now=NOW)

    for key in (KEY, answered, closed, missing):
        assert not _claim(store, key)


def test_two_claims_on_one_row_leave_one_winner(store: Store) -> None:
    _held(store)

    assert [_claim(store), _claim(store)] == [True, False]


def test_settle_waiting_sets_the_reason_and_keeps_the_hold_time(store: Store) -> None:
    _held(store)

    assert _settle(store)

    row = _row(store)
    assert row.state is QuestionState.WAITING_ON_PM
    assert row.waiting_reason is DeclineReason.REQUEST_DECLINED
    assert row.waiting_detail == "not now"
    assert row.claimed_at == NOW
    assert row.updated_at == LATER
    assert not _settle(store)


def test_settle_waiting_refuses_a_claimed_row(store: Store) -> None:
    _held(store)
    assert _claim(store)

    assert not _settle(store)
    assert _row(store).state is QuestionState.CLAIMED


def test_mark_start_attempted_leaves_updated_at(store: Store) -> None:
    _held(store)
    before = _row(store)

    with store.write() as transaction:
        assert mark_start_attempted(
            transaction, KEY, LATER, None, QuestionState.WAITING_ON_REQUEST
        )

    after = _row(store)
    assert after.start_attempted_at == LATER
    assert after.updated_at == before.updated_at


def test_mark_start_attempted_loses_to_a_start_recorded_since_the_read(
    store: Store,
) -> None:
    _held(store)
    with store.write() as transaction:
        assert mark_start_attempted(
            transaction, KEY, NOW, None, QuestionState.WAITING_ON_REQUEST
        )
        assert not mark_start_attempted(
            transaction, KEY, LATER, None, QuestionState.WAITING_ON_REQUEST
        )
        assert mark_start_attempted(
            transaction, KEY, LATER, NOW, QuestionState.WAITING_ON_REQUEST
        )

    assert _row(store).start_attempted_at == LATER


def test_mark_start_attempted_refuses_a_row_no_longer_held(store: Store) -> None:
    _held(store)
    assert _claim(store)

    with store.write() as transaction:
        assert not mark_start_attempted(
            transaction, KEY, LATER, None, QuestionState.WAITING_ON_REQUEST
        )


def test_held_rows_lists_only_held_rows_oldest_first(store: Store) -> None:
    with store.write() as transaction:
        insert_held_row(transaction, SECOND, now=LATER)
        insert_held_row(transaction, KEY, now=NOW)
        insert_question(
            transaction, waiting_question(QuestionKey("run-w", KEY.paused_at)), now=NOW
        )

    with store.read() as transaction:
        rows = held_rows(transaction)

    assert [row.key for row in rows] == [KEY, SECOND]
