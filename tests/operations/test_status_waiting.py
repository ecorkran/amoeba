"""The waiting-on-the-PM entries and their ``run_state`` (slice 224, 3.7)."""

from __future__ import annotations

from dataclasses import replace

from amoeba.answering.values import DeclineReason
from amoeba.operations.status_models import NextOperation, RunState, WaitingEntry
from amoeba.operations.status_waiting import waiting_entries
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.vocabulary import QuestionState
from amoeba.upstream.squadron.run_list import ListedRun
from operations.status_support import in_directory, question_row, recorded_run

PAUSED = "demo-pause-1"
RUNNING = "run-20261111-p6-fe470d63"


def _entries(
    questions: tuple[QuestionRecord, ...], listed: list[ListedRun]
) -> list[WaitingEntry]:
    return [item.entry for item in waiting_entries(questions, listed)]


def _paused_key(run: ListedRun) -> QuestionKey:
    assert run.checkpoint is not None
    assert run.checkpoint.paused_at is not None
    return QuestionKey(run.run_id, run.checkpoint.paused_at)


def test_a_question_at_its_pause_names_answer_with_run_id_and_paused_at() -> None:
    run = recorded_run(PAUSED)
    key = _paused_key(run)
    question = replace(
        question_row(key, QuestionState.WAITING_ON_PM),
        waiting_reason=DeclineReason.CHECK_SAID_NO,
        waiting_detail="not settled",
        slice_label="223 pause-handling",
    )

    (entry,) = _entries((question,), [run])

    assert entry.run_state is RunState.AT_PAUSE
    assert entry.next is not None
    assert entry.next.operation is NextOperation.ANSWER
    assert entry.next.run_id == PAUSED
    assert entry.next.paused_at == key.paused_at
    assert entry.next.directory is None
    assert entry.waiting_reason is DeclineReason.CHECK_SAID_NO
    assert entry.waiting_detail == "not settled"
    assert entry.slice_label == "223 pause-handling"
    assert entry.since == question.claimed_at
    assert entry.detail is None


def test_a_question_whose_run_is_running_has_moved_on_with_no_next() -> None:
    run = recorded_run(RUNNING)
    key = QuestionKey(RUNNING, "2026-11-10T09:00:00+00:00")

    (entry,) = _entries((question_row(key, QuestionState.WAITING_ON_PM),), [run])

    assert entry.run_state is RunState.MOVED_ON
    assert entry.detail == "the run is running"
    assert entry.next is None


def test_a_question_whose_run_paused_again_has_moved_on() -> None:
    run = recorded_run(PAUSED)
    earlier = QuestionKey(PAUSED, "2026-11-09T08:00:00+00:00")

    (entry,) = _entries((question_row(earlier, QuestionState.WAITING_ON_PM),), [run])

    assert entry.run_state is RunState.MOVED_ON
    assert entry.detail is not None
    assert "later pause" in entry.detail
    assert entry.next is None


def test_a_question_for_a_run_no_longer_listed_is_not_listed() -> None:
    gone = QuestionKey("vanished-run", "2026-11-09T08:00:00+00:00")

    (entry,) = _entries((question_row(gone, QuestionState.WAITING_ON_PM),), [])

    assert entry.run_state is RunState.NOT_LISTED
    assert entry.next is None
    assert entry.detail is None


def test_the_run_is_found_across_the_whole_listing_whatever_its_directory() -> None:
    run = in_directory(recorded_run(PAUSED), None)
    key = _paused_key(run)

    (entry,) = _entries((question_row(key, QuestionState.WAITING_ON_PM),), [run])

    assert entry.run_state is RunState.AT_PAUSE


def test_the_order_of_the_open_questions_is_kept() -> None:
    first = question_row(QuestionKey("run-1", "t1"), QuestionState.WAITING_ON_PM)
    second = question_row(QuestionKey("run-2", "t2"), QuestionState.WAITING_ON_PM)

    entries = _entries((first, second), [])

    assert [entry.run_id for entry in entries] == ["run-1", "run-2"]
