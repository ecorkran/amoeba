"""Every exit of a held question, with nobody editing files (slice 242, D3, D8, 7.4).

A ``waiting_on_request`` question ends by: the resume (the request ``done``; also
``test_pause_held.test_a_request_already_done_resumes_the_run_in_the_first_call``),
``waiting_on_pm`` (the request declined), a PM ``answer``, ``dismiss``, and the close
sweep (``run_moved_on``, ``run_gone``). After ``answer`` or ``dismiss`` the request no
longer matters: its end starts nothing. A held question whose resume was refused is
``answered_unresumed`` in ``status``, and ``handle_pause`` delivers the recorded answer
without a second answering run.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

from fake_sq import COMPLETED, poll_not_found, poll_result

from amoeba.answering.values import DeclineReason
from amoeba.operations.answer import AnswerOutcome, answer
from amoeba.operations.dismiss import DismissOutcome, dismiss
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.pause_models import HandlePauseOutcome
from amoeba.operations.question_sweep import sweep_run
from amoeba.operations.request_release import start_ended_held
from amoeba.operations.status import StatusResult, status
from amoeba.operations.status_models import NextOperation, RunEntry
from amoeba.store.answers import answers_of
from amoeba.store.messages import get_message
from amoeba.store.models import QuestionRecord
from amoeba.store.questions import get_question
from amoeba.store.vocabulary import (
    ClosedReason,
    Door,
    QuestionState,
    RequestState,
    ResumeOutcome,
)
from amoeba.upstream.squadron.run_outcome import RunPoll
from operations.handle_rig import (
    KEY,
    PAUSE,
    PAUSED_AT,
    PROJECT_ID,
    RUN,
    RUNNING_DOC,
    World,
    world,
)
from operations.held_support import (
    ADDRESSEE,
    REQUEST_ID,
    add_addressee,
    end_request,
    hold,
    seed_request,
)
from operations.pause_support import START
from operations.status_support import FakeCf, in_directory, recorded_run

LATER = START + timedelta(minutes=5)
#: The held row's re-read, the resume's first look, then the run running.
RESUMING: tuple[RunPoll, ...] = (PAUSE, PAUSE, RUNNING_DOC)
#: The resume's first look, then the run running (``answer``'s own resume).
PM_RESUME: tuple[RunPoll, ...] = (PAUSE, RUNNING_DOC)
#: A Squadron name for a recorded paused run, renamed to this world's run below.
LISTED_PAUSED = "demo-pause-1"


def _row(w: World) -> QuestionRecord:
    with w.store.read() as transaction:
        row = get_question(transaction, KEY)
    assert row is not None
    return row


def _held(w: World, state: RequestState = RequestState.OPEN) -> None:
    add_addressee(w.store)
    seed_request(w.store, state)
    hold(w)


def _starts_nothing_after_the_request_ends(w: World) -> None:
    """End the request, run the start trigger: no ``handle-pause`` child starts."""
    spawned = len(w.spawned.argvs)
    end_request(w.store, RequestState.DONE, now=LATER)

    start_ended_held(w.store, w.config, w.deps)

    assert len(w.spawned.argvs) == spawned


def test_a_held_question_exits_by_the_resume_once_its_request_is_done(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=RESUMING) as w:
        _held(w)
        end_request(w.store, RequestState.DONE, now=LATER)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert _row(w).state is QuestionState.ANSWERED


def test_a_held_question_exits_to_the_pm_when_its_request_is_declined(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=(PAUSE,)) as w:
        _held(w, RequestState.DECLINED)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.WAITING_ON_PM, result
        row = _row(w)
        assert row.state is QuestionState.WAITING_ON_PM
        assert row.waiting_reason is DeclineReason.REQUEST_DECLINED


def test_a_held_question_exits_by_a_pm_answer_and_the_request_no_longer_matters(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=PM_RESUME) as w:
        _held(w)

        result = answer(
            w.store,
            w.config,
            {"run_id": KEY.run_id, "text": "PM says: 250 lines."},
            deps=w.deps,
            via=Door.CLI,
        )

        assert result.outcome is AnswerOutcome.RECORDED
        assert _row(w).state is QuestionState.ANSWERED
        with w.store.read() as transaction:
            (record,) = answers_of(transaction, KEY)
        assert record.resume_outcome is ResumeOutcome.RESUMED
        _starts_nothing_after_the_request_ends(w)


def test_a_held_question_exits_by_dismiss_and_the_request_keeps_its_state(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        _held(w, RequestState.ACCEPTED)

        result = dismiss(
            w.store, {"run_id": KEY.run_id, "reason": "not needed"}, clock=lambda: LATER
        )

        assert result.outcome is DismissOutcome.DISMISSED
        row = _row(w)
        assert (row.state, row.closed_reason) == (
            QuestionState.CLOSED,
            ClosedReason.DISMISSED,
        )
        with w.store.read() as transaction:
            request = get_message(transaction, REQUEST_ID)
        assert request is not None
        assert request.state is RequestState.ACCEPTED
        _starts_nothing_after_the_request_ends(w)


def test_a_held_question_exits_by_the_sweep_once_its_run_moved_on(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        _held(w)

        swept = sweep_run(w.store, w.config, RUN, poll_result(COMPLETED, RUN), LATER)

        assert swept.changed_anything
        row = _row(w)
        assert (row.state, row.closed_reason) == (
            QuestionState.CLOSED,
            ClosedReason.RUN_MOVED_ON,
        )


def test_a_held_question_exits_by_the_sweep_once_its_run_is_gone(
    tmp_path: Path,
) -> None:
    with world(tmp_path) as w:
        _held(w)

        swept = sweep_run(w.store, w.config, RUN, poll_not_found(RUN), LATER)

        assert swept.changed_anything
        row = _row(w)
        assert (row.state, row.closed_reason) == (
            QuestionState.CLOSED,
            ClosedReason.RUN_GONE,
        )


# A refused resume


def _status_entry(w: World, now: datetime) -> RunEntry:
    """This world's run as ``status`` shows it, the run still at its pause."""
    listed = in_directory(recorded_run(LISTED_PAUSED), w.directory)
    assert listed.checkpoint is not None
    listed = replace(
        listed,
        run_id=RUN,
        checkpoint=replace(listed.checkpoint, paused_at=PAUSED_AT),
    )
    deps = replace(
        w.deps,
        cf_run=FakeCf({w.directory: PROJECT_ID}),
        list_runs=lambda: [listed],
        project_names=lambda: {PROJECT_ID: "member-name", ADDRESSEE: "addressee-name"},
        clock=lambda: now,
    )
    result: StatusResult = status(
        w.store, w.config, {}, directory=w.directory, deps=deps
    )
    (entry,) = [
        run
        for program in result.programs
        for member in program.members
        for run in member.runs
    ]
    return entry


def _then_running(w: World) -> None:
    """From now on the run is at its pause once more, then running."""
    polls = iter((PAUSE, PAUSE))

    def poll(run_id: str) -> RunPoll:
        if run_id != RUN:
            return w.answering_poll(run_id)
        return next(polls, RUNNING_DOC)

    w.deps = replace(w.deps, poll_run=poll)


def test_a_refused_resume_shows_handle_pause_and_a_second_call_delivers_it(
    tmp_path: Path,
) -> None:
    # The run never leaves the pause during the first call, so the resume is refused.
    with world(tmp_path, paused_polls=(PAUSE,)) as w:
        _held(w, RequestState.DONE)

        refused = w.handle()

        assert refused.outcome is HandlePauseOutcome.REFUSED, refused
        entry = _status_entry(w, LATER)
        assert entry.pause is PauseClass.ANSWERED_UNRESUMED
        assert entry.next is not None
        assert entry.next.operation is NextOperation.HANDLE_PAUSE
        answering_runs = len(w.spawned.answering)
        _then_running(w)

        delivered = w.handle()

        assert delivered.outcome is HandlePauseOutcome.RESUMED, delivered
        assert len(w.spawned.answering) == answering_runs
        with w.store.read() as transaction:
            (record,) = answers_of(transaction, KEY)
        assert record.resume_outcome is ResumeOutcome.RESUMED
