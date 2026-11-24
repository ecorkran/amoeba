"""``claim_work``: the cap, the limits, the races and the exits (262 tasks 6.2, 6.3)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.answering.values import DeclineReason
from amoeba.operations.steps.dispatch import StepEdges, run_step
from amoeba.operations.steps.limits import MAX_AUTOMATIC_STARTS, MAX_WORK_PER_CLAIM
from amoeba.operations.steps.models import CLAIM_WORK
from amoeba.operations.steps.models_work import (
    ClaimWorkReply,
    HandlePauseItem,
    ResumeItem,
    WakeItem,
)
from amoeba.store.answers import add_pm_answer, get_answer, record_resume
from amoeba.store.questions import get_question
from amoeba.store.vocabulary import QuestionState, ResumeOutcome, WakeOutcome
from amoeba.store.wakes import finish_wake, get_wake
from operations.work_support import (
    CONFIG,
    LOGS,
    PAUSE_LIMIT,
    RESUME_LIMIT,
    START_WAIT,
    Rig,
    answered_question,
    claimed_row,
    held_row,
    key_n,
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


def _kinds(reply: ClaimWorkReply) -> list[str]:
    return [item.kind for item in reply.items]


def test_seven_resumes_waiting_come_five_then_two(rig: Rig) -> None:
    for number in range(1, 8):
        answered_question(rig, number)

    first = rig.claim()
    second = rig.claim()
    third = rig.claim()

    assert len(first.items) == MAX_WORK_PER_CLAIM == 5
    assert len(second.items) == 2
    assert third.items == ()


def test_the_kinds_come_in_order_resumes_held_then_the_oldest_starts_then_wakes(
    rig: Rig,
) -> None:
    wakeable_member(rig)
    claimed_row(rig, 3)
    held_row(rig, 2, "request-done", done=True)
    answered_question(rig, 1)
    rig.advance(PAUSE_LIMIT)

    reply = rig.claim()

    assert _kinds(reply) == ["resume", "handle_pause", "handle_pause", "wake"]
    held, dead = reply.items[1], reply.items[2]
    assert isinstance(held, HandlePauseItem) and held.run_id == key_n(2).run_id
    assert isinstance(dead, HandlePauseItem) and dead.run_id == key_n(3).run_id
    wake = reply.items[3]
    assert isinstance(wake, WakeItem)
    assert wake.log_stem.startswith(f"{LOGS}/wake/")


def test_a_resume_is_handed_out_again_only_once_its_claim_is_the_limit_old(
    rig: Rig,
) -> None:
    seq = answered_question(rig, 1)
    first = rig.claim()
    assert [item.kind for item in first.items] == ["resume"]

    rig.advance(RESUME_LIMIT - SECOND)
    assert rig.claim().items == ()
    rig.advance(SECOND)
    again = rig.claim()

    (item,) = again.items
    assert isinstance(item, ResumeItem) and item.answer_seq == seq
    first_item = first.items[0]
    assert isinstance(first_item, ResumeItem) and item.claim_id != first_item.claim_id


def test_a_start_mark_hands_a_dead_claim_out_again_only_after_the_start_wait(
    rig: Rig,
) -> None:
    claimed_row(rig, 1)
    rig.advance(PAUSE_LIMIT)
    assert _kinds(rig.claim()) == ["handle_pause"]

    rig.advance(START_WAIT - SECOND)
    assert rig.claim().items == ()
    rig.advance(SECOND)

    assert _kinds(rig.claim()) == ["handle_pause"]


def test_a_wake_is_handed_out_again_after_its_deadline_when_nobody_started_it(
    rig: Rig,
) -> None:
    wakeable_member(rig)
    first = rig.claim()
    assert _kinds(first) == ["wake"]
    deadline = timedelta(seconds=CONFIG.wake_timeout_seconds)

    rig.advance(deadline - SECOND)
    assert rig.claim().items == ()
    rig.advance(SECOND)

    assert _kinds(rig.claim()) == ["wake"]


def test_a_dead_claim_is_started_three_times_and_the_fourth_is_starts_exhausted(
    rig: Rig,
) -> None:
    key = claimed_row(rig, 1)
    rig.advance(PAUSE_LIMIT)

    for _ in range(MAX_AUTOMATIC_STARTS):
        assert _kinds(rig.claim()) == ["handle_pause"]
        rig.advance(START_WAIT)
    fourth = rig.claim()

    assert fourth.items == ()
    with rig.store.read() as transaction:
        row = get_question(transaction, key)
    assert row is not None
    assert row.state is QuestionState.WAITING_ON_PM
    assert row.waiting_reason is DeclineReason.STARTS_EXHAUSTED
    assert str(MAX_AUTOMATIC_STARTS) in (row.waiting_detail or "")
    assert "calls log of local" in (row.waiting_detail or "")
    assert not rig.waiting()


def test_a_held_question_that_keeps_failing_is_exhausted_too(rig: Rig) -> None:
    key = held_row(rig, 1, "request-done", done=True)

    for _ in range(MAX_AUTOMATIC_STARTS):
        assert _kinds(rig.claim()) == ["handle_pause"]
        rig.advance(START_WAIT)
    rig.claim()

    with rig.store.read() as transaction:
        row = get_question(transaction, key)
    assert row is not None
    assert row.waiting_reason is DeclineReason.STARTS_EXHAUSTED


def test_a_resume_handed_out_three_times_with_no_outcome_is_then_refused_with_the_count(
    rig: Rig,
) -> None:
    seq = answered_question(rig, 1)

    for _ in range(MAX_AUTOMATIC_STARTS):
        assert _kinds(rig.claim()) == ["resume"]
        rig.advance(RESUME_LIMIT)
    fourth = rig.claim()

    assert fourth.items == ()
    with rig.store.read() as transaction:
        answer = get_answer(transaction, seq)
    assert answer is not None
    assert answer.resume_outcome is ResumeOutcome.REFUSED
    assert str(MAX_AUTOMATIC_STARTS) in (answer.resume_detail or "")
    assert answer.resume_claim_id is None
    # A refused resume is never handed out again.
    rig.advance(RESUME_LIMIT * 10)
    assert rig.claim().items == ()


def test_a_new_answer_after_a_refusal_is_handed_to_that_machines_claim_work(
    rig: Rig,
) -> None:
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
    assert rig.claim().items == ()

    with rig.store.write() as transaction:
        newer = add_pm_answer(transaction, key_n(1), "again", now=rig.now, via=None)

    (item,) = rig.claim().items
    assert isinstance(item, ResumeItem) and item.answer_seq == newer


def test_another_machines_work_is_handed_to_that_machine_only(rig: Rig) -> None:
    seed_as(rig, rig.beta, lambda: answered_question(rig, 1))

    assert rig.claim().items == ()
    rig.as_machine(rig.beta)
    try:
        reply = rig.claim()
    finally:
        rig.as_machine(rig.local)

    assert _kinds(reply) == ["resume"]


@pytest.mark.parametrize("kind", ["resume", "held", "claim", "wake"])
def test_three_callers_at_once_get_one_item_between_them(
    tmp_path: Path, kind: str
) -> None:
    path = tmp_path / "amoeba.sqlite3"
    rig = open_rig(path)
    if kind == "resume":
        answered_question(rig, 1)
    elif kind == "held":
        held_row(rig, 1, "request-done", done=True)
    elif kind == "claim":
        claimed_row(rig, 1)
        rig.advance(PAUSE_LIMIT)
    else:
        wakeable_member(rig)
    now = rig.now
    rig.store.close()
    barrier = threading.Barrier(3)
    replies: list[ClaimWorkReply] = []

    def call() -> None:
        with open_local_store(path) as mine:
            barrier.wait()
            reply = run_step(
                CLAIM_WORK.name,
                mine,
                {"logs_dir": LOGS},
                StepEdges(lambda: now, lambda: CONFIG),
            )
            assert isinstance(reply, ClaimWorkReply)
            replies.append(reply)

    threads = [threading.Thread(target=call) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(len(reply.items) for reply in replies) == 1


def test_each_handed_out_start_adds_one_to_the_start_count(rig: Rig) -> None:
    key = claimed_row(rig, 1)
    rig.advance(PAUSE_LIMIT)

    rig.claim()

    with rig.store.read() as transaction:
        counted = get_question(transaction, key)
    assert counted is not None and counted.start_count == 1


def test_a_finished_wake_for_the_mark_is_not_handed_out_again(rig: Rig) -> None:
    wakeable_member(rig)
    (item,) = rig.claim().items
    assert isinstance(item, WakeItem)
    with rig.store.write() as transaction:
        finish_wake(
            transaction, item.wake_id, WakeOutcome.START_FAILED, None, "no", rig.now
        )
        row = get_wake(transaction, item.wake_id)
    assert row is not None

    rig.advance(timedelta(days=1))

    assert rig.claim().items == ()
