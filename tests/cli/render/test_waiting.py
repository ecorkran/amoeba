"""The text of ``list`` and ``status``, exact (slice 229, D3, task 8.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from amoeba.answering.values import AnsweredBy, DeclineReason
from amoeba.cli.render.text import COLUMNS
from amoeba.cli.render.waiting import (
    NOTHING_NEEDS_YOU,
    render_waiting,
)
from amoeba.operations.calls_log import CallEntry
from amoeba.operations.decisions_models import MemberName
from amoeba.operations.list_view import SettledEntry
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.status_models import (
    ClosedNowEntry,
    MemberStatus,
    NextAction,
    NextOperation,
    ProgramStatus,
    RunEntry,
    StatusOutcome,
    StatusResult,
    UnplacedReason,
    UnplacedRunEntry,
    WaitingEntry,
    WaitingRunState,
)
from amoeba.store.vocabulary import ClosedReason

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
CHECKOUT = Path("/work/core")
PAUSED_AT = "2026-11-14T06:48:00+00:00"
NO_RECORD = (
    "Amoeba has no record of it; it leaves the list when Squadron stops listing it"
)
MEMBER = MemberName(id="id-core", name="core")


def _waiting(question: str = "Which limit?", **fields: object) -> WaitingEntry:
    values: dict[str, object] = {
        "run_id": "run-1",
        "paused_at": PAUSED_AT,
        "question": question,
        "slice_label": None,
        "waiting_reason": DeclineReason.ANSWER_LIMIT_REACHED,
        "waiting_detail": "limit 3",
        "since": NOW - timedelta(hours=5, minutes=12),
        "run_state": WaitingRunState.AT_PAUSE,
        "detail": None,
        "next": None,
    }
    return WaitingEntry.model_validate({**values, **fields})


def _run(run_id: str, pause: PauseClass | None, **fields: object) -> RunEntry:
    handled = pause is not None and pause.value in {
        "unhandled",
        "claim_stale",
        "answered_unresumed",
    }
    values: dict[str, object] = {
        "run_id": run_id,
        "pipeline": "p6",
        "status": "paused" if pause else "running",
        "working_directory": CHECKOUT,
        "checkpoint": None,
        "pause": pause,
        "detail": None,
        "next": NextAction(
            operation=NextOperation.HANDLE_PAUSE,
            run_id=run_id,
            paused_at=PAUSED_AT,
            directory=CHECKOUT,
        )
        if handled
        else None,
    }
    return RunEntry.model_validate({**values, **fields})


def _status(
    *,
    waiting: tuple[WaitingEntry, ...] = (),
    runs: tuple[RunEntry, ...] = (),
    **fields: object,
) -> StatusResult:
    member = MemberStatus(member=MEMBER, runs=runs, waiting_on_pm=waiting)
    program = ProgramStatus(program="trading", members=(member,))
    values: dict[str, object] = {
        "outcome": StatusOutcome.LISTED,
        "programs": (program,),
    }
    return StatusResult.model_validate({**values, **fields})


def _text(result: StatusResult, settled: tuple[SettledEntry, ...] | None = None) -> str:
    return render_waiting(result, now=NOW, settled=settled)


ANSWER = f'      amoeba answer run-1 --paused-at {PAUSED_AT} --text "<your answer>"'
DISMISS = (
    f'      amoeba dismiss run-1 --paused-at {PAUSED_AT} --reason "<why it is closed>"'
)
NOTES = (
    "  A fixed rules file or a raised size cap helps the next question, not these.\n"
    "  A waiting question clears with an answer or a dismiss, or closes when its run "
    "moves on.\n"
)


def test_a_waiting_question_alone() -> None:
    text = _text(_status(waiting=(_waiting(),)))

    assert text == (
        "Waiting on you\n"
        "  core · run-1 · 5h 12m\n"
        "    reason: answer_limit_reached: limit 3\n"
        "    question: Which limit?\n"
        "    answer it, or close it without an answer:\n"
        f"{ANSWER}\n"
        f"{DISMISS}\n" + NOTES
    )


def test_a_waiting_question_whose_run_moved_on_says_so() -> None:
    entry = _waiting(run_state=WaitingRunState.MOVED_ON, detail="completed")

    text = _text(_status(waiting=(entry,)))

    assert "    run: the run has moved on (completed)\n" in text


def test_a_300_character_question_is_cut_and_the_commands_are_whole() -> None:
    text = _text(_status(waiting=(_waiting("q " * 150),)))

    (question,) = [line for line in text.splitlines() if "question:" in line]
    assert len(question) <= COLUMNS
    assert question.endswith("…")
    assert ANSWER in text.splitlines()
    assert "…" not in ANSWER
    assert "  A question cut with … is whole in:\n    amoeba list --json\n" in text


def test_a_question_that_fits_has_no_pointer_to_the_full_text() -> None:
    text = _text(_status(waiting=(_waiting(),)))

    assert "is whole in" not in text


def test_paused_runs_the_hook_missed_show_the_last_call_and_the_command() -> None:
    call = CallEntry(
        at=NOW - timedelta(hours=1),
        run_id="run-9",
        directory="/work/core",
        outcome="skipped",
        reason="not_agent_question",
        detail="the pause was a gate",
    )
    run = _run("run-9", PauseClass.UNHANDLED, last_call=call)

    text = _text(_status(runs=(run,)))

    assert text == (
        "Paused, not handled\n"
        "  core · run-9 · the hook did not run\n"
        "    last call: 2026-11-14 11:00 skipped (not_agent_question) the pause was "
        "a gate\n"
        "    run it in the run's checkout:\n"
        "      cd /work/core && amoeba handle-pause run-9\n"
    )


def test_a_failed_call_shows_its_error() -> None:
    call = CallEntry(
        at=NOW, run_id="run-9", directory="/work/core", error="ContextForgeError",
        detail="cf exited 1",
    )  # fmt: skip
    run = _run("run-9", PauseClass.CLAIM_STALE, last_call=call)

    text = _text(_status(runs=(run,)))

    assert (
        "    last call: 2026-11-14 12:00 error ContextForgeError cf exited 1\n" in text
    )
    assert "answering stopped part-way" in text


def test_an_answer_not_delivered_has_the_command_but_no_last_call() -> None:
    run = _run("run-7", PauseClass.ANSWERED_UNRESUMED)

    text = _text(_status(runs=(run,)))

    assert text == (
        "Paused, not handled\n"
        "  core · run-7 · an answer was recorded but not delivered\n"
        "    run it in the run's checkout:\n"
        "      cd /work/core && amoeba handle-pause run-7\n"
    )


def test_unplaced_runs_say_how_each_clears() -> None:
    runs = (
        UnplacedRunEntry(
            run_id="run-a",
            status="paused",
            reason=UnplacedReason.LOOKUP_FAILED,
            checkpoint_kind="agent_question",
            detail="cf exited 1",
        ),
        UnplacedRunEntry(
            run_id="run-b",
            status="paused",
            reason=UnplacedReason.NO_DIRECTORY,
            checkpoint_kind=None,
        ),
        UnplacedRunEntry(
            run_id="run-c",
            status="paused",
            reason=UnplacedReason.DIRECTORY_MISSING,
            checkpoint_kind=None,
        ),
    )
    text = _text(_status(unplaced_runs=runs))

    assert text == (
        "Unplaced runs\n"
        "  run-a · lookup_failed\n"
        "    detail: cf exited 1\n"
        "    clears once `cf` answers; run this again:\n"
        "      amoeba list\n"
        "  run-b · no_directory\n"
        f"    {NO_RECORD}\n"
        "  run-c · directory_missing\n"
        f"    {NO_RECORD}\n"
    )


def test_problems_list_each_kind() -> None:
    result = _status(
        sweep_problem="the store was busy",
        file_problems=("calls log 2026-11-01 unreadable",),
        problems=("something else",),
    )

    assert _text(result) == (
        "Problems\n"
        "  the store was busy\n"
        "  calls log 2026-11-01 unreadable\n"
        "  something else\n"
    )


def test_nothing_waiting_says_so() -> None:
    assert _text(_status()) == NOTHING_NEEDS_YOU + "\n"


def test_sections_come_in_order_separated_by_a_blank_line() -> None:
    result = _status(
        waiting=(_waiting(),),
        runs=(_run("run-9", PauseClass.UNHANDLED),),
        unplaced_runs=(
            UnplacedRunEntry(
                run_id="run-b",
                status="paused",
                reason=UnplacedReason.NO_DIRECTORY,
                checkpoint_kind=None,
            ),
        ),
        sweep_problem="busy",
    )

    text = _text(result)

    headings = [line for line in text.splitlines() if line and not line.startswith(" ")]
    assert headings == [
        "Waiting on you",
        "Paused, not handled",
        "Unplaced runs",
        "Problems",
    ]
    assert "\n\nPaused, not handled\n" in text


def test_what_this_call_closed_is_listed_after_the_sections() -> None:
    closed = ClosedNowEntry(
        program="trading",
        member=MEMBER,
        run_id="run-4",
        paused_at=PAUSED_AT,
        question="Which?",
        closed_reason=ClosedReason.RUN_MOVED_ON,
        closed_detail="completed",
    )

    text = _text(_status(closed_now=(closed,)))

    assert text == (
        f"{NOTHING_NEEDS_YOU}\n\n"
        "Closed by this check\n"
        "  core · run-4 · run_moved_on: completed\n"
    )


def _settled(**fields: object) -> SettledEntry:
    values: dict[str, object] = {
        "program": "trading",
        "member_id": "id-core",
        "member_name": "core",
        "run_id": "run-2",
        "paused_at": PAUSED_AT,
        "question": "Which branch?",
        "ended": AnsweredBy.PM,
        "settled_at": NOW - timedelta(days=2),
    }
    return SettledEntry.model_validate({**values, **fields})


def test_all_adds_every_other_run_then_settled() -> None:
    result = _status(
        runs=(
            _run("run-9", PauseClass.UNHANDLED),
            _run("run-3", None),
            _run("run-5", PauseClass.WAITING_ON_PM),
        )
    )

    text = _text(result, (_settled(), _settled(ended=ClosedReason.DISMISSED)))

    assert text.split("\n\nOther runs\n")[1] == (
        "  core\n"
        "    run-3 · running\n"
        "    run-5 · paused · waiting_on_pm\n"
        "\n"
        "Settled\n"
        "  2026-11-12 · core · answered by you\n"
        "    question: Which branch?\n"
        "  2026-11-12 · core · dismissed\n"
        "    question: Which branch?\n"
    )
    assert "run-9 · running" not in text.split("Other runs")[1]


def test_settled_names_a_member_cf_no_longer_lists_by_its_id() -> None:
    text = _text(_status(), (_settled(member_name=None),))

    assert "  2026-11-12 · id-core (not in Context Forge) · answered by you\n" in text


def test_without_settled_there_is_no_other_runs_or_settled_section() -> None:
    text = _text(_status(runs=(_run("run-3", None),)))

    assert "Other runs" not in text
    assert "Settled" not in text


def test_a_rejected_result_prints_its_problems() -> None:
    result = StatusResult(
        outcome=StatusOutcome.REJECTED,
        rejection=RejectCode.UNKNOWN_PROGRAM,
        problems=("unknown program 'x'; known programs: trading",),
    )

    assert _text(result) == (
        "rejected: unknown_program: unknown program 'x'; known programs: trading\n"
    )
