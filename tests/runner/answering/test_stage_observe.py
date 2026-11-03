"""The stage's observe pass: finish what ended, leave what runs (slice 144, D10)."""

from __future__ import annotations

from pathlib import Path

from sq_stub_scripts import check_reply, proposed_answer_reply

from amoeba.process import PollFailure, RunOutcome
from amoeba.runner.answering.finish import RESULT_QUESTION_OUTCOME, QuestionOutcome
from amoeba.runner.faults import FaultKind, TickFaults
from amoeba.store import JournalOutcome, QuestionState, Store
from runner.answering.launch_rig import (
    budget,
    build_stage_rig,
    run_document,
    write_replies,
)


def test_a_finished_run_is_finished(store: Store, tmp_path: Path) -> None:
    rig = build_stage_rig(tmp_path, store)
    entry = rig.start(rig.launch.record)
    write_replies(
        entry, proposed_answer_reply("use main", ["P1"]), check_reply("yes", "ok")
    )
    rig.poll.answers.append(run_document(entry, RunOutcome.COMPLETED))

    result = rig.run()

    resolved = store.journal_entry(entry.id)
    record = store.question(rig.launch.record.id)
    assert result.wrote and not result.cut_off
    assert resolved is not None and resolved.outcome is JournalOutcome.COMPLETED
    assert resolved.result is not None
    assert resolved.result[RESULT_QUESTION_OUTCOME] == QuestionOutcome.SUBMITTED.value
    assert record is not None and record.state is QuestionState.ANSWERED
    assert rig.launch.context.tracker.get(entry.id) is None


def test_an_in_flight_run_is_left_alone(store: Store, tmp_path: Path) -> None:
    rig = build_stage_rig(tmp_path, store)
    entry = rig.start(rig.launch.record)
    rig.poll.answers.append(run_document(entry, RunOutcome.TIMED_OUT))

    rig.run()

    unresolved = store.journal_entry(entry.id)
    record = store.question(rig.launch.record.id)
    assert unresolved is not None and not unresolved.is_resolved
    assert record is not None and record.state is QuestionState.ANSWERING


def test_a_spent_budget_polls_nothing_and_reports_the_cut(
    store: Store, tmp_path: Path
) -> None:
    rig = build_stage_rig(tmp_path, store)
    entry = rig.start(rig.launch.record)

    result = rig.run(allowed=0)

    assert result.cut_off
    assert rig.poll.asked == []
    unresolved = store.journal_entry(entry.id)
    assert unresolved is not None and not unresolved.is_resolved


def test_a_run_observed_before_the_budget_ran_out_is_still_finished(
    store: Store, tmp_path: Path
) -> None:
    rig = build_stage_rig(tmp_path, store)
    first = rig.start(rig.launch.record)
    second = rig.start(rig.launch.ask_another())
    write_replies(first, {"kind": "decline", "reason": "no basis"}, None)
    rig.poll.answers.append(run_document(first, RunOutcome.COMPLETED))

    result = rig.run(allowed=1)

    done = store.journal_entry(first.id)
    waiting = store.journal_entry(second.id)
    assert result.cut_off
    assert done is not None and done.is_resolved
    assert waiting is not None and not waiting.is_resolved


def test_a_poll_failure_is_raised_against_its_node(
    store: Store, tmp_path: Path
) -> None:
    rig = build_stage_rig(tmp_path, store)
    entry = rig.start(rig.launch.record)
    rig.poll.answers.append(PollFailure("sq exploded"))
    faults = TickFaults()

    rig.stage.run(budget(), faults)

    [fault] = list(faults)
    assert fault.kind is FaultKind.RUN_OBSERVATION_FAILED
    assert fault.node_id == entry.node_id
