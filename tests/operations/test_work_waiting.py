"""``work_waiting``: each row of D10's table, true and false (slice 262, 6.1)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store.seed import mark_wake_wanted

from amoeba.operations.steps.resume import ResumeClaimed, claim_resume
from amoeba.store.answers import record_resume
from amoeba.store.held_questions import mark_start_attempted
from amoeba.store.vocabulary import QuestionState, ResumeOutcome
from operations.work_support import (
    PAUSE_LIMIT,
    RESUME_LIMIT,
    START_WAIT,
    Rig,
    answered_question,
    claimed_row,
    held_row,
    open_rig,
    seed_as,
    wakeable_member,
)

SECOND = timedelta(seconds=1)


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    opened = open_rig(tmp_path / "amoeba.sqlite3")
    yield opened
    opened.store.close()


def test_a_store_with_no_work_has_none(rig: Rig) -> None:
    assert not rig.waiting()


def test_an_answer_with_no_outcome_and_no_claim_is_a_resume_waiting(rig: Rig) -> None:
    answered_question(rig, 1)

    assert rig.waiting()


def test_a_resume_claim_blocks_the_flag_until_it_is_the_limit_old(rig: Rig) -> None:
    seq = answered_question(rig, 1)
    with rig.store.write() as transaction:
        claim = claim_resume(transaction, seq, rig.now, RESUME_LIMIT.total_seconds())
    assert isinstance(claim, ResumeClaimed)

    rig.advance(RESUME_LIMIT - SECOND)
    assert not rig.waiting()
    rig.advance(SECOND)

    assert rig.waiting()


def test_a_refused_resume_is_not_work(rig: Rig) -> None:
    seq = answered_question(rig, 1)
    with rig.store.write() as transaction:
        record_resume(
            transaction,
            seq,
            ResumeOutcome.REFUSED,
            detail="why",
            log=None,
            at=rig.now,
            claim_id=None,
        )

    assert not rig.waiting()


@pytest.mark.parametrize("final", [ResumeOutcome.RESUMED, ResumeOutcome.NOT_DELIVERED])
def test_a_resume_with_a_final_outcome_is_not_work(
    rig: Rig, final: ResumeOutcome
) -> None:
    seq = answered_question(rig, 1)
    with rig.store.write() as transaction:
        record_resume(
            transaction, seq, final, detail=None, log=None, at=rig.now, claim_id=None
        )

    assert not rig.waiting()


def test_a_held_question_whose_request_is_done_is_work_and_an_open_one_is_not(
    rig: Rig,
) -> None:
    held_row(rig, 1, "request-open", done=False)
    assert not rig.waiting()

    held_row(rig, 2, "request-done", done=True)

    assert rig.waiting()


def test_a_held_question_started_within_the_wait_is_not_work_until_it_has_passed(
    rig: Rig,
) -> None:
    key = held_row(rig, 1, "request-done", done=True)
    with rig.store.write() as transaction:
        assert mark_start_attempted(
            transaction, key, rig.now, None, QuestionState.WAITING_ON_REQUEST
        )

    rig.advance(START_WAIT - SECOND)
    assert not rig.waiting()
    rig.advance(SECOND)

    assert rig.waiting()


def test_a_held_question_whose_request_is_gone_is_work(rig: Rig) -> None:
    held_row(rig, 1, "request-gone", done=False)
    with rig.store.write() as transaction:
        transaction.execute("PRAGMA foreign_keys = OFF")
        transaction.execute("DELETE FROM messages WHERE message_id = 'request-gone'")

    assert rig.waiting()


def test_a_claim_is_work_once_stale_and_not_before(rig: Rig) -> None:
    claimed_row(rig, 1)

    rig.advance(PAUSE_LIMIT - SECOND)
    assert not rig.waiting()
    rig.advance(SECOND)

    assert rig.waiting()


def test_a_stale_claim_started_within_the_wait_is_not_work(rig: Rig) -> None:
    key = claimed_row(rig, 1)
    rig.advance(PAUSE_LIMIT)
    with rig.store.write() as transaction:
        assert mark_start_attempted(
            transaction, key, rig.now, None, QuestionState.CLAIMED
        )

    assert not rig.waiting()
    rig.advance(START_WAIT)
    assert rig.waiting()


def test_a_wake_due_for_a_member_with_a_wakeable_checkout_here_is_work(
    rig: Rig,
) -> None:
    wakeable_member(rig)

    assert rig.waiting()


def test_no_mark_or_a_wake_command_elsewhere_is_no_wake_work(rig: Rig) -> None:
    with rig.store.write() as transaction:
        mark_wake_wanted(transaction, "member-b", rig.now)
    assert not rig.waiting()  # a mark, but no wakeable checkout on this machine


def test_another_machines_rows_are_not_this_machines_work(rig: Rig) -> None:
    seed_as(rig, rig.beta, lambda: answered_question(rig, 1))
    seed_as(rig, rig.beta, lambda: claimed_row(rig, 2))
    rig.advance(PAUSE_LIMIT)

    assert not rig.waiting()
    assert rig.waiting(rig.beta)
