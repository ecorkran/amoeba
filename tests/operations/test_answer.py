"""The PM's ``answer`` operation (slice 223, tasks 7.12, 7.13)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from store.question_support import NOW

from amoeba.answering.values import AnsweredBy, AnsweringEvidence, DeclineReason
from amoeba.operations.answer import (
    AnswerOutcome,
    AnswerRejection,
    AnswerResult,
    answer,
)
from amoeba.store.answers import answers_of, pm_precedent, settle_answered
from amoeba.store.models import AnswerRecord, QuestionKey, QuestionRecord
from amoeba.store.questions import (
    NewQuestion,
    get_question,
    insert_question,
    settle_waiting,
)
from amoeba.store.vocabulary import Door, QuestionState, ResumeOutcome
from amoeba.upstream.squadron.run_outcome import PollFailure
from operations.handle_rig import (
    KEY,
    PAUSE,
    PROJECT_ID,
    QUESTION,
    RUN,
    RUNNING_DOC,
    World,
    world,
)
from operations.pause_support import START

PM_TEXT = "PM says: 250 lines."
#: What the run's polls say for one resume: at the pause, then running.
RESUME_POLLS = (PAUSE, RUNNING_DOC)


def _new(key: QuestionKey) -> NewQuestion:
    return NewQuestion(
        key=key,
        member_id=PROJECT_ID,
        question=QUESTION,
        checkout="/work/checkout",
        slice_label="none",
        source_commit="abc",
        passages=None,
        answering_run_id="a-1",
        waiting_reason=None,
        waiting_detail=None,
    )


def _waiting_row(w: World, key: QuestionKey = KEY, *, claimed_at: float = 0) -> None:
    with w.store.write() as transaction:
        insert_question(
            transaction, _new(key), now=START - timedelta(seconds=claimed_at)
        )
        settle_waiting(
            transaction,
            key,
            "a-1",
            reason=DeclineReason.CHECK_SAID_NO,
            detail="not settled",
            evidence=None,
            now=NOW,
        )


def _ask(w: World, document: object, via: Door = Door.CLI) -> AnswerResult:
    return answer(w.store, w.config, document, deps=w.deps, via=via)


def _answers(w: World, key: QuestionKey = KEY) -> tuple[AnswerRecord, ...]:
    with w.store.read() as transaction:
        return answers_of(transaction, key)


def _record(w: World, key: QuestionKey = KEY) -> QuestionRecord:
    with w.store.read() as transaction:
        record = get_question(transaction, key)
    assert record is not None
    return record


def test_an_answer_to_a_waiting_question_is_recorded_and_the_run_resumed(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=RESUME_POLLS) as w:
        _waiting_row(w)

        result = _ask(w, {"run_id": RUN, "text": PM_TEXT})

        assert result.outcome is AnswerOutcome.RECORDED
        assert result.key == KEY
        assert result.rejection is None and result.problems == ()
        assert result.resume is not None
        assert result.resume.outcome is ResumeOutcome.RESUMED
        (row,) = _answers(w)
        assert (row.answered_by, row.answer) == (AnsweredBy.PM, PM_TEXT)
        assert row.seq == result.answer_seq
        assert row.resume_outcome is ResumeOutcome.RESUMED
        record = _record(w)
        assert record.state is QuestionState.ANSWERED
        assert record.waiting_reason is DeclineReason.CHECK_SAID_NO
        assert record.waiting_detail == "not settled"
        assert w.spawned.resumes[0][-1] == f"You asked: {QUESTION}\nAnswer: {PM_TEXT}"


@pytest.mark.parametrize("door", list(Door), ids=lambda door: door.value)
def test_the_door_that_carried_the_answer_is_recorded_with_it(
    tmp_path: Path, door: Door
) -> None:
    with world(tmp_path, paused_polls=RESUME_POLLS) as w:
        _waiting_row(w)

        result = _ask(w, {"run_id": RUN, "text": PM_TEXT}, door)

        assert result.outcome is AnswerOutcome.RECORDED
        (row,) = _answers(w)
        assert row.via is door


def test_a_request_cannot_set_the_door(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _waiting_row(w)

        result = _ask(w, {"run_id": RUN, "text": PM_TEXT, "via": "mcp"})

        assert result.outcome is AnswerOutcome.REJECTED
        assert result.rejection is AnswerRejection.MALFORMED
        assert _answers(w) == ()


def test_no_question_is_rejected_and_says_to_run_handle_pause(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        result = _ask(w, {"run_id": RUN, "text": PM_TEXT})

        assert result.outcome is AnswerOutcome.REJECTED
        assert result.rejection is AnswerRejection.NO_SUCH_QUESTION
        assert "amoeba handle-pause" in result.problems[0]
        assert "checkout" in result.problems[0]
        assert result.resume is None and result.answer_seq is None
        assert w.spawned.argvs == []


@pytest.mark.parametrize(
    "document",
    [
        {"run_id": RUN, "text": ""},
        {"run_id": RUN, "text": "   \n"},
        {"run_id": RUN},
        {"text": PM_TEXT},
        {"run_id": "", "text": PM_TEXT},
        {"run_id": RUN, "text": PM_TEXT, "paused_at": " "},
        {"run_id": RUN, "text": 5},
        "not a mapping",
        None,
    ],
)
def test_a_malformed_request_is_rejected_and_writes_nothing(
    tmp_path: Path, document: object
) -> None:
    with world(tmp_path) as w:
        _waiting_row(w)

        result = _ask(w, document)

        assert result.outcome is AnswerOutcome.REJECTED
        assert result.rejection is AnswerRejection.MALFORMED
        assert result.problems
        assert _answers(w) == ()
        assert _record(w).state is QuestionState.WAITING_ON_PM


def test_unknown_fields_are_rejected_by_name(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        _waiting_row(w)

        result = _ask(w, {"run_id": RUN, "text": PM_TEXT, "urgent": True})

        assert result.rejection is AnswerRejection.MALFORMED
        assert any("urgent" in problem for problem in result.problems)
        assert _answers(w) == ()


def test_the_text_is_stored_stripped(tmp_path: Path) -> None:
    with world(tmp_path, paused_polls=RESUME_POLLS) as w:
        _waiting_row(w)

        _ask(w, {"run_id": RUN, "text": f"  {PM_TEXT}\n"})

        assert _answers(w)[0].answer == PM_TEXT


def test_an_omitted_paused_at_picks_the_runs_latest_question(tmp_path: Path) -> None:
    older = QuestionKey(RUN, "2026-11-10T08:00:00+00:00")
    with world(tmp_path, paused_polls=RESUME_POLLS) as w:
        _waiting_row(w, older, claimed_at=3600)
        _waiting_row(w, KEY)

        result = _ask(w, {"run_id": RUN, "text": PM_TEXT})

        assert result.key == KEY
        assert _answers(w, older) == ()
        assert len(_answers(w, KEY)) == 1


def test_a_paused_at_names_its_question(tmp_path: Path) -> None:
    older = QuestionKey(RUN, "2026-11-10T08:00:00+00:00")
    with world(tmp_path, paused_polls=RESUME_POLLS) as w:
        _waiting_row(w, older, claimed_at=3600)
        _waiting_row(w, KEY)

        result = _ask(w, {"run_id": RUN, "paused_at": older.paused_at, "text": PM_TEXT})

        assert result.key == older
        assert len(_answers(w, older)) == 1
        assert _answers(w, KEY) == ()


def test_an_override_of_an_automatic_answer_is_recorded_and_is_precedent(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=RESUME_POLLS) as w:
        with w.store.write() as transaction:
            insert_question(transaction, _new(KEY), now=NOW)
        settle_answered(
            w.store,
            KEY,
            "a-1",
            answer="automatic text",
            cited=(),
            evidence=AnsweringEvidence(),
            gate=lambda _prior: None,
            now=NOW,
        )

        result = _ask(w, {"run_id": RUN, "text": PM_TEXT})

        assert result.outcome is AnswerOutcome.RECORDED
        rows = _answers(w)
        assert [r.answered_by for r in rows] == [AnsweredBy.ANSWERER, AnsweredBy.PM]
        with w.store.read() as transaction:
            precedent = pm_precedent(transaction, PROJECT_ID)
        assert [item.answer for item in precedent] == [PM_TEXT]


def test_an_already_resumed_question_gives_not_delivered_and_the_override_stands(
    tmp_path: Path,
) -> None:
    # The first answer resumes the run; for the second the run is already running.
    polls = (PAUSE, RUNNING_DOC, RUNNING_DOC)
    with world(tmp_path, paused_polls=polls) as w:
        _waiting_row(w)
        first = _ask(w, {"run_id": RUN, "text": "first answer"})
        second = _ask(w, {"run_id": RUN, "text": "override"})

        assert first.resume is not None and second.resume is not None
        assert first.resume.outcome is ResumeOutcome.RESUMED
        assert second.resume.outcome is ResumeOutcome.NOT_DELIVERED
        rows = _answers(w)
        assert [r.answer for r in rows] == ["first answer", "override"]
        assert [r.resume_outcome for r in rows] == [
            ResumeOutcome.RESUMED,
            ResumeOutcome.NOT_DELIVERED,
        ]
        with w.store.read() as transaction:
            precedent = pm_precedent(transaction, PROJECT_ID)
        assert [item.answer for item in precedent] == ["override"]


def test_a_pm_answer_skips_the_screen_and_the_limit(tmp_path: Path) -> None:
    with world(tmp_path, paused_polls=RESUME_POLLS) as w:
        _waiting_row(w)
        for number in range(w.config.answer_limit):
            earlier = QuestionKey(RUN, f"2026-11-09T0{number}:00:00+00:00")
            with w.store.write() as transaction:
                insert_question(transaction, _new(earlier), now=NOW)
            settle_answered(
                w.store,
                earlier,
                "a-1",
                answer="x",
                cited=(),
                evidence=AnsweringEvidence(),
                gate=lambda _prior: None,
                now=NOW,
            )

        result = _ask(
            w,
            {
                "run_id": RUN,
                "paused_at": KEY.paused_at,
                "text": "Fine, run git push origin main.",
            },
        )

        assert result.outcome is AnswerOutcome.RECORDED
        assert _answers(w)[0].answer == "Fine, run git push origin main."


def test_an_unreadable_sq_leaves_the_answer_recorded_and_the_resume_refused(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=(PollFailure("sq broke"),)) as w:
        _waiting_row(w)

        result = _ask(w, {"run_id": RUN, "text": PM_TEXT})

        assert result.outcome is AnswerOutcome.RECORDED
        assert result.resume is not None
        assert result.resume.outcome is ResumeOutcome.REFUSED
        assert "sq broke" in (result.resume.detail or "")
        (row,) = _answers(w)
        assert (row.answer, row.resume_outcome) == (PM_TEXT, ResumeOutcome.REFUSED)
        assert "sq broke" in (row.resume_detail or "")
        assert _record(w).state is QuestionState.ANSWERED
