"""The text of the one-result commands, exact (slice 229, D2, task 8.5)."""

from __future__ import annotations

from datetime import UTC, datetime

from amoeba.answering.values import AnsweredBy, DeclineReason
from amoeba.cli.render.simple import (
    render_answer,
    render_decisions,
    render_dismiss,
    render_handle_pause,
    render_mark_read,
    render_retract,
)
from amoeba.cli.render.text import COLUMNS
from amoeba.operations.answer import AnswerOutcome, AnswerRejection, AnswerResult
from amoeba.operations.decisions_models import (
    DecisionsOutcome,
    DecisionsRecord,
    DecisionsResult,
    MemberName,
    ResumeRecord,
)
from amoeba.operations.dismiss import DismissOutcome, DismissRejection, DismissResult
from amoeba.operations.mark_read import MarkReadOutcome, MarkReadResult
from amoeba.operations.pause_models import (
    HandlePauseOutcome,
    HandlePauseResult,
    ResumeResult,
    SkipReason,
)
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.retract import RetractOutcome, RetractRejection, RetractResult
from amoeba.store.models import QuestionKey
from amoeba.store.vocabulary import ClosedReason, ResumeOutcome

KEY = QuestionKey("run-1", "2026-11-14T06:48:00+00:00")
WHEN = datetime(2026, 11, 14, 7, 30, tzinfo=UTC)


def test_a_recorded_answer_that_resumed() -> None:
    result = AnswerResult(
        outcome=AnswerOutcome.RECORDED,
        key=KEY,
        answer_seq=5,
        resume=ResumeResult(ResumeOutcome.RESUMED, None, "/logs/resume.log"),
    )

    assert render_answer(result) == (
        "recorded\n"
        "  question: run-1 at 2026-11-14T06:48:00+00:00\n"
        "  answer: #5\n"
        "  resume: resumed\n"
    )


def test_a_recorded_answer_whose_resume_was_refused_shows_why() -> None:
    result = AnswerResult(
        outcome=AnswerOutcome.RECORDED,
        key=KEY,
        answer_seq=5,
        resume=ResumeResult(ResumeOutcome.REFUSED, "the run is not paused", None),
    )

    assert render_answer(result).splitlines()[-2:] == [
        "  resume: refused",
        "    detail: the run is not paused",
    ]


def test_a_rejected_answer() -> None:
    result = AnswerResult(
        outcome=AnswerOutcome.REJECTED,
        rejection=AnswerRejection.NO_SUCH_QUESTION,
        problems=("no question for run-9",),
    )

    assert render_answer(result) == (
        "rejected: no_such_question: no question for run-9\n"
    )


def test_a_dismissed_question_and_a_repeat() -> None:
    dismissed = DismissResult(
        outcome=DismissOutcome.DISMISSED,
        key=KEY,
        closed_reason=ClosedReason.DISMISSED,
        closed_detail="not needed",
    )
    repeat = DismissResult(
        outcome=DismissOutcome.UNCHANGED,
        key=KEY,
        closed_reason=ClosedReason.RUN_MOVED_ON,
        closed_detail="completed",
    )

    assert render_dismiss(dismissed) == (
        "dismissed: run-1 at 2026-11-14T06:48:00+00:00\n"
        "  closed: dismissed\n"
        "  detail: not needed\n"
    )
    assert render_dismiss(repeat).splitlines()[0] == (
        "unchanged: run-1 at 2026-11-14T06:48:00+00:00"
    )


def test_a_rejected_dismiss() -> None:
    result = DismissResult(
        outcome=DismissOutcome.REJECTED,
        rejection=DismissRejection.NOT_OPEN,
        problems=("the question is not open",),
    )

    assert render_dismiss(result) == "rejected: not_open: the question is not open\n"


def test_a_retracted_answer_unchanged_and_rejected() -> None:
    retracted = RetractResult(outcome=RetractOutcome.RETRACTED, answer_seq=5, key=KEY)
    unchanged = RetractResult(outcome=RetractOutcome.UNCHANGED, answer_seq=5, key=KEY)
    rejected = RetractResult(
        outcome=RetractOutcome.REJECTED,
        rejection=RetractRejection.NO_SUCH_ANSWER,
        problems=("no answer 9",),
    )

    assert render_retract(retracted) == (
        "retracted: answer #5\n  question: run-1 at 2026-11-14T06:48:00+00:00\n"
    )
    assert render_retract(unchanged).splitlines()[0] == "unchanged: answer #5"
    assert render_retract(rejected) == "rejected: no_such_answer: no answer 9\n"


def test_mark_read_moved_unchanged_and_rejected() -> None:
    moved = MarkReadResult(outcome=MarkReadOutcome.MOVED, previous=3, current=7)
    unchanged = MarkReadResult(outcome=MarkReadOutcome.UNCHANGED, previous=7, current=7)
    rejected = MarkReadResult(
        outcome=MarkReadOutcome.REJECTED,
        rejection=RejectCode.BEYOND_LAST_RECORD,
        problems=("9 is beyond the last record, 7",),
    )

    assert render_mark_read(moved) == "moved: marker 3 -> 7\n"
    assert render_mark_read(unchanged) == "unchanged: marker at 7\n"
    assert render_mark_read(rejected) == (
        "rejected: beyond_last_record: 9 is beyond the last record, 7\n"
    )


def _record(seq: int, answered_by: AnsweredBy, **fields: object) -> DecisionsRecord:
    values: dict[str, object] = {
        "seq": seq,
        "recorded_at": WHEN,
        "program": "trading",
        "member": MemberName(id="id-core", name="core"),
        "run_id": "run-1",
        "paused_at": KEY.paused_at,
        "slice_label": None,
        "question": "Which limit?",
        "answered_by": answered_by,
        "via": None,
        "answer": "Three hundred lines.",
        "prior_answer_seq": None,
        "based_on": None,
        "resume": ResumeRecord(outcome=None, detail=None, at=None),
        "retracted_at": None,
        "retract_reason": None,
    }
    return DecisionsRecord.model_validate({**values, **fields})


def test_decisions_list_each_answer_and_the_mark_read_command() -> None:
    result = DecisionsResult(
        outcome=DecisionsOutcome.LISTED,
        records=(_record(4, AnsweredBy.ANSWERER), _record(5, AnsweredBy.PM)),
        read_through=5,
        marker=3,
    )

    assert render_decisions(result) == (
        "2 answers (marker at 3)\n"
        "  #4 · 2026-11-14 07:30 · core · answered by the answerer\n"
        "    question: Which limit?\n"
        "    answer: Three hundred lines.\n"
        "  #5 · 2026-11-14 07:30 · core · answered by you\n"
        "    question: Which limit?\n"
        "    answer: Three hundred lines.\n"
        "when you have read them:\n"
        "  amoeba mark-read --through 5\n"
    )


def test_a_long_answer_is_cut_and_a_retraction_is_shown() -> None:
    record = _record(
        6,
        AnsweredBy.PM,
        answer="long " * 100,
        retracted_at=WHEN,
        retract_reason="wrong repo",
    )
    result = DecisionsResult(
        outcome=DecisionsOutcome.LISTED, records=(record,), marker=3
    )

    lines = render_decisions(result).splitlines()

    (answer,) = [line for line in lines if "answer: " in line]
    assert len(answer) <= COLUMNS
    assert answer.endswith("…")
    assert "    retracted: wrong repo" in lines
    assert not any("mark-read" in line for line in lines)


def test_decisions_with_nothing_and_rejected() -> None:
    empty = DecisionsResult(outcome=DecisionsOutcome.LISTED, marker=3)
    rejected = DecisionsResult(
        outcome=DecisionsOutcome.REJECTED,
        rejection=RejectCode.UNKNOWN_PROGRAM,
        problems=("unknown program 'x'",),
    )

    assert render_decisions(empty) == "no answers to show (marker at 3)\n"
    assert render_decisions(rejected) == (
        "rejected: unknown_program: unknown program 'x'\n"
    )


def test_a_single_answer_is_not_pluralised() -> None:
    result = DecisionsResult(
        outcome=DecisionsOutcome.LISTED,
        records=(_record(4, AnsweredBy.PM),),
        marker=3,
    )

    assert render_decisions(result).startswith("1 answer (marker at 3)\n")


def test_handle_pause_is_one_line_per_outcome() -> None:
    cases = {
        HandlePauseResult(HandlePauseOutcome.RESUMED): "answered\n",
        HandlePauseResult(
            HandlePauseOutcome.REFUSED, detail="the run moved on"
        ): "answered, resume refused: the run moved on\n",
        HandlePauseResult(
            HandlePauseOutcome.NOT_DELIVERED, detail="no child"
        ): "answered, not delivered: no child\n",
        HandlePauseResult(
            HandlePauseOutcome.WAITING_ON_PM,
            waiting_reason=DeclineReason.ANSWER_LIMIT_REACHED,
            detail="limit 3",
        ): "waiting_on_pm: answer_limit_reached: limit 3\n",
        HandlePauseResult(
            HandlePauseOutcome.SKIPPED, skip_reason=SkipReason.PROMPT_ONLY
        ): "skipped: prompt_only\n",
        HandlePauseResult(HandlePauseOutcome.SUPERSEDED): "superseded\n",
    }

    for result, expected in cases.items():
        assert render_handle_pause(result) == expected


def test_a_long_handle_pause_detail_stays_on_one_line() -> None:
    result = HandlePauseResult(HandlePauseOutcome.SKIPPED, detail="why " * 100)

    text = render_handle_pause(result)

    assert text.count("\n") == 1
    assert len(text.rstrip("\n")) <= COLUMNS
