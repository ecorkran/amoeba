"""Closing, dismissing and reading open questions (slice 228, D4, D5)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from amoeba.store.answers import (
    add_pm_answer,
    latest_answer,
    mark_not_delivered,
    mark_resume_started,
    record_resume,
    retract_answer,
)
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.question_closing import (
    close_question,
    dismiss_question,
    member_open_questions,
    open_rows_of_run,
    sweep_candidates,
)
from amoeba.store.questions import get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason, QuestionState, ResumeOutcome
from store.question_support import (
    KEY,
    MEMBER_ID,
    NOW,
    OTHER_MEMBER_ID,
    claimed_question,
    seed_members,
    waiting_question,
)

LATER = NOW + timedelta(minutes=5)
SECOND = QuestionKey(KEY.run_id, "2026-11-10T13:00:00+00:00")
THIRD = QuestionKey(KEY.run_id, "2026-11-10T14:00:00+00:00")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def _row(store: Store, key: QuestionKey = KEY) -> QuestionRecord:
    with store.read() as transaction:
        row = get_question(transaction, key)
    assert row is not None
    return row


def _seed_waiting(store: Store, key: QuestionKey = KEY) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(key), now=NOW)


def _close(store: Store, row: QuestionRecord, *, detail: str = "gone") -> bool:
    with store.write() as transaction:
        return close_question(
            transaction,
            row.key,
            ClosedReason.RUN_MOVED_ON,
            detail,
            row.state,
            row.updated_at,
            LATER,
        )


def _dismiss(store: Store, key: QuestionKey = KEY) -> bool:
    with store.write() as transaction:
        current = get_question(transaction, key)
        assert current is not None
        return dismiss_question(transaction, current, "not needed", now=LATER)


def _answer_unresumed(store: Store, key: QuestionKey) -> int:
    with store.write() as transaction:
        return add_pm_answer(transaction, key, "answer", now=NOW, via=None)


def test_close_question_closes_a_matching_row(store: Store) -> None:
    _seed_waiting(store)
    before = _row(store)

    assert _close(store, before, detail="completed")

    after = _row(store)
    assert after.state is QuestionState.CLOSED
    assert after.closed_reason is ClosedReason.RUN_MOVED_ON
    assert after.closed_detail == "completed"
    assert after.closed_at == LATER
    assert after.updated_at == LATER


def test_a_changed_updated_at_or_state_closes_nothing(store: Store) -> None:
    _seed_waiting(store)
    stale = _row(store)
    _answer_unresumed(store, KEY)  # moves state and updated_at
    answered = _row(store)

    assert not _close(store, stale)
    with store.write() as transaction:
        wrong_state = close_question(
            transaction,
            KEY,
            ClosedReason.RUN_GONE,
            None,
            QuestionState.WAITING_ON_PM,
            answered.updated_at,
            LATER,
        )

    assert not wrong_state
    assert _row(store) == answered


def test_two_racing_closers_leave_one_winner(store: Store) -> None:
    _seed_waiting(store)
    seen = _row(store)

    first = _close(store, seen, detail="first")
    second = _close(store, seen, detail="second")

    assert (first, second) == (True, False)
    assert _row(store).closed_detail == "first"


def test_writers_on_two_connections_compare_and_set_one_waiting_row(
    tmp_path: Path,
) -> None:
    path = tmp_path / "shared.sqlite3"
    with Store.open(path) as first, Store.open(path) as second:
        seed_members(first)
        _seed_waiting(first)
        stale = _row(second)

        _answer_unresumed(first, KEY)  # the first writer wins
        assert not _close(second, stale)  # the stale closer loses
        assert _row(second).state is QuestionState.ANSWERED

        assert _dismiss(second)  # an unresumed answer is dismissable (D5)
        assert not _dismiss(first)  # and a second dismissal finds it closed

        _answer_unresumed(first, KEY)  # a PM answer reopens a closed question
        reopened = _row(second)
        assert reopened.state is QuestionState.ANSWERED
        assert reopened.closed_reason is ClosedReason.DISMISSED  # kept as history


@pytest.mark.parametrize("state", ["claimed", "waiting_on_pm"])
def test_dismiss_closes_a_claimed_or_waiting_question(store: Store, state: str) -> None:
    with store.write() as transaction:
        new = claimed_question() if state == "claimed" else waiting_question()
        insert_question(transaction, new, now=NOW)

    assert _dismiss(store)

    row = _row(store)
    assert row.state is QuestionState.CLOSED
    assert row.closed_reason is ClosedReason.DISMISSED
    assert row.closed_detail == "not needed"


@pytest.mark.parametrize("outcome", [None, ResumeOutcome.REFUSED])
def test_dismiss_closes_an_answered_question_and_marks_its_answer_not_delivered(
    store: Store, outcome: ResumeOutcome | None
) -> None:
    _seed_waiting(store)
    seq = _answer_unresumed(store, KEY)
    if outcome is not None:
        with store.write() as transaction:
            record_resume(transaction, seq, outcome, detail="lock", log="/log", at=NOW)

    assert _dismiss(store)

    assert _row(store).state is QuestionState.CLOSED
    with store.read() as transaction:
        answer = latest_answer(transaction, KEY)
    assert answer is not None
    assert answer.resume_outcome is ResumeOutcome.NOT_DELIVERED
    assert answer.resume_detail == "dismissed"
    assert answer.resume_log == ("/log" if outcome is not None else None)


@pytest.mark.parametrize(
    "outcome", [ResumeOutcome.RESUMED, ResumeOutcome.NOT_DELIVERED]
)
def test_dismiss_refuses_an_answered_question_whose_answer_is_final(
    store: Store, outcome: ResumeOutcome
) -> None:
    _seed_waiting(store)
    seq = _answer_unresumed(store, KEY)
    with store.write() as transaction:
        record_resume(transaction, seq, outcome, detail=None, log=None, at=NOW)
    before = _row(store)

    assert not _dismiss(store)

    assert _row(store) == before


def test_dismiss_refuses_a_closed_question(store: Store) -> None:
    _seed_waiting(store)
    assert _dismiss(store)

    assert not _dismiss(store)


def _seed_every_state(store: Store) -> None:
    """KEY waiting, SECOND answered unresumed, THIRD answered and resumed; a closed
    FOURTH; and another member's waiting question."""
    fourth = QuestionKey(KEY.run_id, "2026-11-10T15:00:00+00:00")
    with store.write() as transaction:
        insert_question(transaction, waiting_question(KEY), now=NOW)
        insert_question(transaction, claimed_question(SECOND), now=NOW)
        insert_question(transaction, waiting_question(THIRD), now=NOW)
        insert_question(transaction, waiting_question(fourth), now=NOW)
        insert_question(
            transaction,
            waiting_question(
                QuestionKey("other-run", KEY.paused_at), member_id=OTHER_MEMBER_ID
            ),
            now=NOW,
        )
        add_pm_answer(transaction, SECOND, "unresumed", now=NOW, via=None)
        third_seq = add_pm_answer(transaction, THIRD, "resumed", now=NOW, via=None)
        record_resume(
            transaction, third_seq, ResumeOutcome.RESUMED, detail=None, log=None, at=NOW
        )
    _dismiss(store, fourth)


def test_open_rows_hold_each_open_state_and_leave_out_closed_and_settled(
    store: Store,
) -> None:
    _seed_every_state(store)

    with store.read() as transaction:
        of_run = open_rows_of_run(transaction, KEY.run_id)

    assert [row.key for row in of_run] == [KEY, SECOND]
    assert [row.state for row in of_run] == [
        QuestionState.WAITING_ON_PM,
        QuestionState.ANSWERED,
    ]


def test_sweep_candidates_and_member_open_questions_read_the_same_rows(
    store: Store,
) -> None:
    _seed_every_state(store)

    with store.read() as transaction:
        members = sweep_candidates(transaction, [MEMBER_ID, OTHER_MEMBER_ID])
        mine = member_open_questions(transaction, MEMBER_ID)
        nobody = sweep_candidates(transaction, [])

    assert [row.key for row in mine] == [KEY, SECOND]
    assert [row.key.run_id for row in members] == [KEY.run_id, KEY.run_id, "other-run"]
    assert nobody == ()


def test_an_answered_question_with_a_delivered_answer_is_not_a_members_open_question(
    store: Store,
) -> None:
    _seed_waiting(store)
    seq = _answer_unresumed(store, KEY)
    with store.read() as transaction:
        assert len(member_open_questions(transaction, MEMBER_ID)) == 1
    with store.write() as transaction:
        record_resume(
            transaction, seq, ResumeOutcome.RESUMED, detail=None, log=None, at=NOW
        )

    with store.read() as transaction:
        assert member_open_questions(transaction, MEMBER_ID) == ()


def test_retract_sets_once_and_reports_a_repeat(store: Store) -> None:
    _seed_waiting(store)
    seq = _answer_unresumed(store, KEY)

    with store.write() as transaction:
        first = retract_answer(transaction, seq, "wrong", now=LATER)
        second = retract_answer(transaction, seq, "again", now=NOW)
        missing = retract_answer(transaction, seq + 99, "none", now=NOW)

    assert (first, second, missing) == (True, False, False)
    with store.read() as transaction:
        answer = latest_answer(transaction, KEY)
    assert answer is not None
    assert answer.retracted_at == LATER
    assert answer.retract_reason == "wrong"


def test_mark_not_delivered_never_overwrites_a_resumed_answer(store: Store) -> None:
    _seed_waiting(store)
    seq = _answer_unresumed(store, KEY)
    with store.write() as transaction:
        record_resume(
            transaction, seq, ResumeOutcome.RESUMED, detail=None, log=None, at=NOW
        )
        assert not mark_not_delivered(transaction, seq, "late", now=LATER)

    with store.read() as transaction:
        answer = latest_answer(transaction, KEY)
    assert answer is not None
    assert answer.resume_outcome is ResumeOutcome.RESUMED


@pytest.mark.parametrize("final", [ResumeOutcome.RESUMED, ResumeOutcome.NOT_DELIVERED])
def test_mark_resume_started_is_refused_once_the_outcome_is_final(
    store: Store, final: ResumeOutcome
) -> None:
    _seed_waiting(store)
    seq = _answer_unresumed(store, KEY)
    with store.write() as transaction:
        assert mark_resume_started(transaction, seq, now=LATER)  # first resume
        record_resume(
            transaction, seq, ResumeOutcome.REFUSED, detail="x", log=None, at=NOW
        )
        assert mark_resume_started(transaction, seq, now=LATER)  # a retry
        record_resume(transaction, seq, final, detail=None, log=None, at=NOW)

        assert not mark_resume_started(transaction, seq, now=LATER)

    with store.read() as transaction:
        answer = latest_answer(transaction, KEY)
    assert answer is not None
    assert answer.resume_started_at == LATER


def test_a_pm_answer_on_a_closed_question_sets_answered_and_keeps_the_reason(
    store: Store,
) -> None:
    _seed_waiting(store)
    assert _dismiss(store)

    _answer_unresumed(store, KEY)

    row = _row(store)
    assert row.state is QuestionState.ANSWERED
    assert row.closed_reason is ClosedReason.DISMISSED
    assert row.closed_detail == "not needed"
