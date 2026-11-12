"""``sweep_run``: every row of the D4 table, and its races (slice 228, D4)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fake_sq import COMPLETED, LOCK_BEFORE, PAUSED_AGENT_QUESTION, poll_result
from store.question_support import (
    MEMBER_ID,
    NOW,
    claimed_question,
    seed_members,
    waiting_question,
)
from user_configs import user_config

from amoeba.operations.question_sweep import (
    RunFate,
    SweepResult,
    apply_sweep,
    fate_of_poll,
    sweep_run,
)
from amoeba.operations.resume import resume_bound_seconds
from amoeba.store.answers import (
    add_pm_answer,
    latest_answer,
    mark_resume_started,
    record_resume,
)
from amoeba.store.models import AnswerRecord, QuestionKey, QuestionRecord
from amoeba.store.questions import dismiss_question, get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason, QuestionState, ResumeOutcome
from amoeba.upstream.squadron.run_outcome import RunOutcome, RunOutcomeDocument

RUN = "demo-run"
CONFIG = user_config()
WAIT = CONFIG.answering_wait_seconds
PAUSE = poll_result(PAUSED_AGENT_QUESTION, RUN)
assert PAUSE.checkpoint is not None
CURRENT = PAUSE.checkpoint.paused_at_text or ""
OLD = QuestionKey(RUN, "2026-11-01T08:00:00+00:00")
NEW = QuestionKey(RUN, CURRENT)
COMPLETED_DOC = poll_result(COMPLETED, RUN)
OTHER_PAUSE = poll_result(LOCK_BEFORE, RUN)
GONE = RunOutcomeDocument(run_id=RUN, outcome=RunOutcome.NOT_FOUND)
UNREADABLE = RunOutcomeDocument(run_id=RUN, outcome=RunOutcome.UNREADABLE)
BOUND = timedelta(seconds=resume_bound_seconds(CONFIG))


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        yield opened


def _sweep(
    store: Store, polled: RunOutcomeDocument, *, after: timedelta
) -> SweepResult:
    return sweep_run(store, CONFIG, RUN, polled, NOW + after)


def _row(store: Store, key: QuestionKey) -> QuestionRecord:
    with store.read() as transaction:
        row = get_question(transaction, key)
    assert row is not None
    return row


def _waiting(store: Store, key: QuestionKey) -> None:
    with store.write() as transaction:
        insert_question(transaction, waiting_question(key), now=NOW)


def _latest(store: Store, key: QuestionKey) -> AnswerRecord:
    with store.read() as transaction:
        found = latest_answer(transaction, key)
    assert found is not None
    return found


def _answered(store: Store, key: QuestionKey) -> int:
    _waiting(store, key)
    with store.write() as transaction:
        return add_pm_answer(transaction, key, "the answer", now=NOW)


def test_a_waiting_row_at_an_older_pause_closes_as_moved_on_with_the_later_pause(
    store: Store,
) -> None:
    _waiting(store, OLD)
    _waiting(store, NEW)

    result = _sweep(store, PAUSE, after=timedelta(minutes=1))

    assert [c.key for c in result.closed] == [OLD]
    closed = _row(store, OLD)
    assert closed.state is QuestionState.CLOSED
    assert closed.closed_reason is ClosedReason.RUN_MOVED_ON
    assert closed.closed_detail == f"paused at {CURRENT}"
    assert closed.closed_at == NOW + timedelta(minutes=1)
    assert result.problem is None


def test_a_row_at_the_runs_current_pause_is_never_touched(store: Store) -> None:
    _waiting(store, NEW)
    before = _row(store, NEW)

    result = _sweep(store, PAUSE, after=timedelta(days=30))

    assert not result.changed_anything
    assert _row(store, NEW) == before


def test_a_completed_run_closes_every_open_row_with_its_state(store: Store) -> None:
    _waiting(store, OLD)
    _waiting(store, NEW)

    result = _sweep(store, COMPLETED_DOC, after=timedelta(minutes=1))

    assert sorted(c.key.paused_at for c in result.closed) == sorted(
        [OLD.paused_at, NEW.paused_at]
    )
    assert {c.closed_detail for c in result.closed} == {"completed"}
    assert {c.closed_reason for c in result.closed} == {ClosedReason.RUN_MOVED_ON}


def test_a_run_sq_no_longer_knows_closes_its_rows_as_gone(store: Store) -> None:
    _waiting(store, OLD)

    result = _sweep(store, GONE, after=timedelta(minutes=1))

    (closed,) = result.closed
    assert closed.closed_reason is ClosedReason.RUN_GONE
    assert closed.closed_detail == "not_found"
    assert closed.member_id == MEMBER_ID


def test_an_old_claim_closes_and_a_young_one_stays(store: Store) -> None:
    with store.write() as transaction:
        insert_question(transaction, claimed_question(OLD), now=NOW)

    young = _sweep(store, COMPLETED_DOC, after=timedelta(seconds=WAIT - 1))
    assert not young.changed_anything
    assert _row(store, OLD).state is QuestionState.CLAIMED

    old = _sweep(store, COMPLETED_DOC, after=timedelta(seconds=WAIT))

    assert [c.key for c in old.closed] == [OLD]
    assert _row(store, OLD).state is QuestionState.CLOSED


def test_an_unresumed_answer_past_the_bound_becomes_not_delivered(
    store: Store,
) -> None:
    seq = _answered(store, OLD)

    result = _sweep(store, COMPLETED_DOC, after=BOUND)

    (undelivered,) = result.undelivered
    assert (undelivered.key, undelivered.answer_seq) == (OLD, seq)
    assert undelivered.resume_outcome is ResumeOutcome.NOT_DELIVERED
    answer = _latest(store, OLD)
    assert answer.resume_outcome is ResumeOutcome.NOT_DELIVERED
    assert answer.resume_detail == "completed"
    assert _row(store, OLD).state is QuestionState.ANSWERED  # no new question state


def test_an_answer_inside_the_bound_stays_including_one_with_a_fresh_resume_start(
    store: Store,
) -> None:
    seq = _answered(store, OLD)
    just_inside = BOUND - timedelta(seconds=1)
    assert not _sweep(store, COMPLETED_DOC, after=just_inside).changed_anything

    with store.write() as transaction:
        mark_resume_started(transaction, seq, now=NOW + BOUND)  # a retry in flight

    result = _sweep(store, COMPLETED_DOC, after=BOUND + just_inside)

    assert not result.changed_anything
    assert _latest(store, OLD).resume_outcome is None


def test_a_refused_answer_is_judged_from_its_newest_sign_of_life(store: Store) -> None:
    seq = _answered(store, OLD)
    with store.write() as transaction:
        record_resume(
            transaction,
            seq,
            ResumeOutcome.REFUSED,
            detail="lock",
            log=None,
            at=NOW + BOUND,
        )

    assert not _sweep(store, COMPLETED_DOC, after=BOUND + BOUND / 2).changed_anything
    assert _sweep(store, COMPLETED_DOC, after=BOUND + BOUND).undelivered


def test_a_delivered_answer_is_left_alone(store: Store) -> None:
    seq = _answered(store, OLD)
    with store.write() as transaction:
        record_resume(
            transaction, seq, ResumeOutcome.RESUMED, detail=None, log=None, at=NOW
        )

    assert not _sweep(store, COMPLETED_DOC, after=BOUND * 10).changed_anything


def test_an_unreadable_run_closes_nothing(store: Store) -> None:
    _waiting(store, OLD)

    assert not _sweep(store, UNREADABLE, after=timedelta(days=1)).changed_anything
    assert _row(store, OLD).state is QuestionState.WAITING_ON_PM


def test_a_paused_run_without_a_pause_time_closes_nothing(store: Store) -> None:
    _waiting(store, OLD)
    undated = RunOutcomeDocument(run_id=RUN, outcome=RunOutcome.PAUSED)

    assert fate_of_poll(undated) is None
    assert not _sweep(store, undated, after=timedelta(days=1)).changed_anything
    assert _row(store, OLD).state is QuestionState.WAITING_ON_PM


FATE = RunFate(ClosedReason.RUN_MOVED_ON, "completed", None)


def test_a_concurrent_answer_between_read_and_write_wins(store: Store) -> None:
    _waiting(store, OLD)
    stale = _row(store, OLD)
    with store.write() as transaction:
        add_pm_answer(transaction, OLD, "the PM got there first", now=NOW)

    result = apply_sweep(store, CONFIG, [(stale, FATE)], NOW + timedelta(minutes=1))

    assert not result.changed_anything
    assert _row(store, OLD).state is QuestionState.ANSWERED


def test_a_concurrent_dismiss_between_read_and_write_wins(store: Store) -> None:
    _waiting(store, OLD)
    stale = _row(store, OLD)
    with store.write() as transaction:
        assert dismiss_question(transaction, stale, "dismissed first", now=NOW)

    result = apply_sweep(store, CONFIG, [(stale, FATE)], NOW + timedelta(minutes=1))

    assert not result.changed_anything
    assert _row(store, OLD).closed_reason is ClosedReason.DISMISSED


def test_a_busy_write_is_reported_as_a_problem_and_raises_nothing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "busy.sqlite3"
    with Store.open(path, busy_timeout_seconds=0.1) as store:
        seed_members(store)
        _waiting(store, OLD)
        holder = sqlite3.connect(path, isolation_level=None)
        holder.execute("BEGIN IMMEDIATE")
        try:
            result = _sweep(store, COMPLETED_DOC, after=timedelta(minutes=1))
        finally:
            holder.close()

        assert result.problem is not None
        assert "could not close stale questions" in result.problem
        assert not result.changed_anything
        assert _row(store, OLD).state is QuestionState.WAITING_ON_PM


def test_fate_of_poll_covers_every_outcome() -> None:
    assert fate_of_poll(UNREADABLE) is None
    unknown = RunOutcomeDocument(run_id=RUN, outcome=RunOutcome.UNKNOWN_STATUS)
    assert fate_of_poll(unknown) is None
    timed_out = RunOutcomeDocument(run_id=RUN, outcome=RunOutcome.TIMED_OUT)
    assert fate_of_poll(timed_out) == RunFate(
        ClosedReason.RUN_MOVED_ON, "running", None
    )
    assert fate_of_poll(PAUSE) == RunFate(
        ClosedReason.RUN_MOVED_ON, f"paused at {CURRENT}", CURRENT
    )
