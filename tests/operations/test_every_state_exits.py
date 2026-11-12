"""Every state a question can be in has an exit, with nobody editing files (slice 228,
Integration Requirements). Each test walks one state to one of its exits through the
operations, and none touches a file or SQL.

It covers every state: ``claimed`` (settle, dead claim, sweep, dismiss),
``waiting_on_pm`` (answer, sweep, dismiss), ``answered`` and unresumed (resume, sweep,
dismiss), ``answered`` and settled (terminal), ``closed`` (terminal; ``answer``
reopens it) and a retracted answer (terminal; a new answer replaces it).
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fake_sq import COMPLETED, poll_result
from store.question_support import NOW, claimed_question, waiting_question

from amoeba.answering.values import AnsweringEvidence, DeclineReason
from amoeba.operations.answer import AnswerOutcome, answer
from amoeba.operations.dismiss import (
    DismissOutcome,
    DismissRejection,
    dismiss,
)
from amoeba.operations.question_sweep import SweepResult, sweep_run
from amoeba.operations.resume import resume_bound_seconds
from amoeba.operations.retract import RetractOutcome, retract
from amoeba.store.answers import (
    Settled,
    add_pm_answer,
    answers_of,
    pm_precedent,
    settle_answered,
)
from amoeba.store.models import QuestionRecord
from amoeba.store.questions import get_question, insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason, QuestionState, ResumeOutcome
from operations.handle_rig import (
    KEY,
    PAUSE,
    PROJECT_ID,
    RUNNING_DOC,
    World,
    world,
)
from operations.pause_support import START

RESUME_POLLS = (PAUSE, RUNNING_DOC)
ANSWERING_RUN = "amoeba-20261110T110000Z-aaaaaaaaaaaa"
LATER = NOW + timedelta(minutes=5)


def _state(store: Store) -> QuestionRecord:
    with store.read() as transaction:
        row = get_question(transaction, KEY)
    assert row is not None
    return row


def _claim(w: World) -> None:
    with w.store.write() as transaction:
        insert_question(
            transaction,
            claimed_question(KEY, member_id=PROJECT_ID, answering_run_id=ANSWERING_RUN),
            now=NOW,
        )


def _wait(w: World) -> None:
    with w.store.write() as transaction:
        insert_question(
            transaction, waiting_question(KEY, member_id=PROJECT_ID), now=NOW
        )


def _dismiss(w: World) -> DismissOutcome:
    return dismiss(
        w.store, {"run_id": KEY.run_id, "reason": "not needed"}, clock=lambda: LATER
    ).outcome


def _answer(w: World, text: str = "PM says: 250 lines.") -> AnswerOutcome:
    return answer(
        w.store, w.config, {"run_id": KEY.run_id, "text": text}, deps=w.deps
    ).outcome


def _precedent(w: World) -> list[str]:
    with w.store.read() as transaction:
        return [item.answer for item in pm_precedent(transaction, PROJECT_ID)]


def test_claimed_exits_by_the_answering_run_settling(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _claim(w)

        settled = settle_answered(
            w.store,
            KEY,
            ANSWERING_RUN,
            answer="300 lines",
            cited=(),
            evidence=AnsweringEvidence(),
            gate=lambda _prior: None,
            now=LATER,
        )

        assert isinstance(settled, Settled)
        assert _state(w.store).state is QuestionState.ANSWERED


def test_claimed_exits_by_the_dead_claim_path(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        with w.store.write() as transaction:
            insert_question(
                transaction,
                claimed_question(
                    KEY, member_id=PROJECT_ID, answering_run_id=ANSWERING_RUN
                ),
                now=START - timedelta(days=1),
            )

        w.handle()

        assert _state(w.store).state is not QuestionState.CLAIMED


def test_claimed_exits_by_dismiss(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _claim(w)

        assert _dismiss(w) is DismissOutcome.DISMISSED

        assert _state(w.store).state is QuestionState.CLOSED


def test_waiting_on_pm_exits_by_answer(tmp_path: Path) -> None:
    with world(tmp_path, paused_polls=RESUME_POLLS) as w:
        _wait(w)

        assert _answer(w) is AnswerOutcome.RECORDED

        assert _state(w.store).state is QuestionState.ANSWERED


def test_waiting_on_pm_exits_by_dismiss_including_at_the_answer_limit(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        _wait(w)
        assert _state(w.store).waiting_reason is DeclineReason.ANSWER_LIMIT_REACHED

        assert _dismiss(w) is DismissOutcome.DISMISSED

        assert _state(w.store).state is QuestionState.CLOSED


def test_closed_is_terminal_and_answer_reopens_it(tmp_path: Path) -> None:
    with world(tmp_path, paused_polls=RESUME_POLLS) as w:
        _wait(w)
        _dismiss(w)

        assert _dismiss(w) is DismissOutcome.UNCHANGED  # nothing more to do to it

        assert _answer(w) is AnswerOutcome.RECORDED  # the way out, if it was a mistake
        reopened = _state(w.store)
        assert reopened.state is QuestionState.ANSWERED
        assert reopened.closed_reason is ClosedReason.DISMISSED


def test_a_retracted_answer_is_terminal_and_a_new_answer_replaces_it(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=(*RESUME_POLLS, *RESUME_POLLS)) as w:
        _wait(w)
        _answer(w, "first")
        with w.store.read() as transaction:
            (first,) = answers_of(transaction, KEY)
        retracted = retract(
            w.store,
            {"answer_seq": first.seq, "reason": "wrong"},
            clock=lambda: LATER,
        )
        assert retracted.outcome is RetractOutcome.RETRACTED
        assert _precedent(w) == []

        _answer(w, "second")

        assert _precedent(w) == ["second"]


def test_answered_and_settled_is_terminal(tmp_path: Path) -> None:
    with world(tmp_path, paused_polls=RESUME_POLLS) as w:
        _wait(w)
        _answer(w)
        with w.store.read() as transaction:
            (delivered,) = answers_of(transaction, KEY)
        assert delivered.resume_outcome is ResumeOutcome.RESUMED

        result = dismiss(
            w.store, {"run_id": KEY.run_id, "reason": "x"}, clock=lambda: LATER
        )

        assert result.outcome is DismissOutcome.REJECTED
        assert result.rejection is DismissRejection.NOT_OPEN
        assert _state(w.store).state is QuestionState.ANSWERED


# The automatic sweep: the exit of a question whose run has moved on (7.8).

COMPLETED_RUN = poll_result(COMPLETED, KEY.run_id)


def _sweep(w: World, after: timedelta) -> SweepResult:
    return sweep_run(w.store, w.config, KEY.run_id, COMPLETED_RUN, NOW + after)


def test_claimed_exits_by_the_sweep_once_it_is_old_enough(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _claim(w)
        wait = timedelta(seconds=w.config.answering_wait_seconds)

        assert not _sweep(w, wait - timedelta(seconds=1)).changed_anything
        assert _sweep(w, wait).changed_anything

        row = _state(w.store)
        assert row.state is QuestionState.CLOSED
        assert row.closed_reason is ClosedReason.RUN_MOVED_ON


def test_waiting_on_pm_exits_by_the_sweep(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _wait(w)

        assert _sweep(w, timedelta(minutes=1)).changed_anything

        assert _state(w.store).state is QuestionState.CLOSED


def test_answered_unresumed_exits_by_the_sweep(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _wait(w)
        with w.store.write() as transaction:
            add_pm_answer(transaction, KEY, "an answer", now=NOW)
        bound = timedelta(seconds=resume_bound_seconds(w.config))

        assert not _sweep(w, bound - timedelta(seconds=1)).changed_anything
        assert _sweep(w, bound).undelivered

        with w.store.read() as transaction:
            (record,) = answers_of(transaction, KEY)
        assert record.resume_outcome is ResumeOutcome.NOT_DELIVERED


def test_answered_unresumed_exits_by_the_hook_resuming_it(tmp_path: Path) -> None:
    # The hook's own poll, then the resume's polls.
    with world(tmp_path, paused_polls=(PAUSE, *RESUME_POLLS)) as w:
        _wait(w)
        with w.store.write() as transaction:
            add_pm_answer(transaction, KEY, "an answer", now=NOW)

        w.handle()

        with w.store.read() as transaction:
            (record,) = answers_of(transaction, KEY)
        assert record.resume_outcome is ResumeOutcome.RESUMED


def test_answered_unresumed_exits_by_dismiss(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _wait(w)
        with w.store.write() as transaction:
            add_pm_answer(transaction, KEY, "an answer", now=NOW)

        assert _dismiss(w) is DismissOutcome.DISMISSED

        assert _state(w.store).state is QuestionState.CLOSED
        with w.store.read() as transaction:
            (record,) = answers_of(transaction, KEY)
        assert record.resume_outcome is ResumeOutcome.NOT_DELIVERED
