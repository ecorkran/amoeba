"""``settled_since``: answered and closed questions inside a window (slice 229)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from amoeba.answering.values import AnsweredBy
from amoeba.store.answers import add_pm_answer, record_resume
from amoeba.store.models import QuestionKey
from amoeba.store.question_closing import close_question
from amoeba.store.questions import get_question, insert_question
from amoeba.store.row_values import encode_timestamp
from amoeba.store.settled import SettledQuestion, settled_since
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import ClosedReason, QuestionState, ResumeOutcome
from store.question_support import (
    NOW,
    OTHER_MEMBER_ID,
    claimed_question,
    seed_members,
    waiting_question,
)

WINDOW_START = NOW - timedelta(days=30)
INSIDE = NOW - timedelta(days=2)
NEWER = NOW - timedelta(days=1)
OUTSIDE = NOW - timedelta(days=45)


def _key(name: str) -> QuestionKey:
    return QuestionKey(f"run-{name}", f"{NOW.date()}T10:00:00+00:00")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def _open(
    transaction: Transaction, name: str, *, member: str | None = None
) -> QuestionKey:
    key = _key(name)
    new = (
        claimed_question(key)
        if member is None
        else claimed_question(key, member_id=member)
    )
    insert_question(transaction, new, now=OUTSIDE)
    return key


def _close(
    transaction: Transaction, key: QuestionKey, reason: ClosedReason, at: datetime
) -> None:
    current = get_question(transaction, key)
    assert current is not None
    assert close_question(
        transaction, key, reason, None, current.state, current.updated_at, at
    )


def _answer_pm(
    transaction: Transaction,
    key: QuestionKey,
    at: datetime,
    outcome: ResumeOutcome | None,
) -> int:
    seq = add_pm_answer(transaction, key, "yes", now=at, via=None)
    if outcome is not None:
        record_resume(transaction, seq, outcome, detail=None, log=None, at=at)
    return seq


def _answer_automatically(
    transaction: Transaction, key: QuestionKey, at: datetime
) -> None:
    transaction.execute(
        "INSERT INTO answers (run_id, paused_at, answered_by, answer, recorded_at, "
        "resume_outcome) VALUES (?, ?, ?, 'ok', ?, ?)",
        (
            key.run_id,
            key.paused_at,
            AnsweredBy.ANSWERER.value,
            encode_timestamp(at),
            ResumeOutcome.RESUMED.value,
        ),
    )
    transaction.execute(
        "UPDATE questions SET state = ? WHERE run_id = ? AND paused_at = ?",
        (QuestionState.ANSWERED.value, key.run_id, key.paused_at),
    )


def _settled(
    store: Store, since: datetime = WINDOW_START
) -> tuple[SettledQuestion, ...]:
    with store.read() as transaction:
        return settled_since(transaction, since)


def test_closed_and_answered_questions_inside_the_window_are_newest_first(
    store: Store,
) -> None:
    with store.write() as transaction:
        closed = _open(transaction, "closed")
        _close(transaction, closed, ClosedReason.DISMISSED, INSIDE)
        by_pm = _open(transaction, "pm")
        _answer_pm(transaction, by_pm, NEWER, ResumeOutcome.RESUMED)
        by_answerer = _open(transaction, "auto", member=OTHER_MEMBER_ID)
        _answer_automatically(transaction, by_answerer, NOW - timedelta(hours=1))

    rows = _settled(store)

    assert [(row.key, row.ended) for row in rows] == [
        (by_answerer, AnsweredBy.ANSWERER),
        (by_pm, AnsweredBy.PM),
        (closed, ClosedReason.DISMISSED),
    ]
    assert [row.settled_at for row in rows] == sorted(
        (row.settled_at for row in rows), reverse=True
    )
    assert rows[0].program_id == "demo"
    assert rows[0].member_id == OTHER_MEMBER_ID
    assert rows[0].question == "What is the file length limit?"


def test_a_question_that_settled_before_the_window_is_absent(store: Store) -> None:
    with store.write() as transaction:
        _close(transaction, _open(transaction, "old"), ClosedReason.RUN_GONE, OUTSIDE)
        _answer_pm(
            transaction, _open(transaction, "oldpm"), OUTSIDE, ResumeOutcome.RESUMED
        )

    assert _settled(store) == ()


def test_the_window_start_is_inclusive(store: Store) -> None:
    with store.write() as transaction:
        key = _open(transaction, "edge")
        _close(transaction, key, ClosedReason.RUN_MOVED_ON, WINDOW_START)

    assert [row.key for row in _settled(store)] == [key]


def test_an_open_question_is_never_settled(store: Store) -> None:
    with store.write() as transaction:
        _open(transaction, "claimed")
        insert_question(transaction, waiting_question(_key("waiting")), now=NEWER)
        _answer_pm(transaction, _open(transaction, "unresumed"), NEWER, None)
        _answer_pm(
            transaction, _open(transaction, "refused"), NEWER, ResumeOutcome.REFUSED
        )

    assert _settled(store) == ()


def test_an_answer_that_can_no_longer_be_delivered_is_settled(store: Store) -> None:
    with store.write() as transaction:
        key = _open(transaction, "undelivered")
        _answer_pm(transaction, key, NEWER, ResumeOutcome.NOT_DELIVERED)

    assert [row.key for row in _settled(store)] == [key]


def test_a_later_answer_decides_not_an_earlier_one(store: Store) -> None:
    with store.write() as transaction:
        key = _open(transaction, "twice")
        _answer_pm(transaction, key, INSIDE, ResumeOutcome.RESUMED)
        _answer_pm(transaction, key, NEWER, None)  # a new answer, not yet resumed

    assert _settled(store) == ()


def test_a_dismissed_answered_question_is_listed_once_as_closed(store: Store) -> None:
    with store.write() as transaction:
        key = _open(transaction, "dismissed")
        _answer_pm(transaction, key, INSIDE, ResumeOutcome.NOT_DELIVERED)
        _close(transaction, key, ClosedReason.DISMISSED, NEWER)

    assert [(row.key, row.ended) for row in _settled(store)] == [
        (key, ClosedReason.DISMISSED)
    ]


def test_a_removed_members_questions_are_still_settled(store: Store) -> None:
    with store.write() as transaction:
        key = _open(transaction, "gone")
        _close(transaction, key, ClosedReason.DISMISSED, NEWER)
        transaction.execute(
            "UPDATE members SET removed_at = ? WHERE project_id = ?",
            (encode_timestamp(NOW), "member-a"),
        )

    assert [row.key for row in _settled(store)] == [key]
