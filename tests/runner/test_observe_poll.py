"""Observation of confirmed runs: poll cadence, classification, ordering."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.process import RunOutcome
from amoeba.runner.budget import TickResult
from amoeba.runner.decide import RunState
from amoeba.runner.faults import FaultKind
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.runner.observed import RunEnded, RunVanished
from amoeba.store import PARAM_RUN_ID
from runner.observe_support import (
    INTERVAL,
    Child,
    Rig,
    document,
    entry,
    failure,
)


def test_an_entry_without_a_handle_is_confirmed_and_polled(tmp_path: Path) -> None:
    rig = Rig(tmp_path, document("run-1", RunOutcome.TIMED_OUT))

    observed = rig.observe(entry())

    assert rig.poll.asked == ["run-1"]
    assert observed.runs[0].run.state is RunState.RUNNING
    assert observed.result is TickResult.COMPLETE


def test_a_confirmed_run_is_not_polled_before_the_interval(tmp_path: Path) -> None:
    rig = Rig(
        tmp_path,
        document("run-1", RunOutcome.TIMED_OUT),
        document("run-1", RunOutcome.TIMED_OUT),
    )
    e = entry()
    rig.observe(e)

    rig.clock.seconds = INTERVAL - 1
    again = rig.observe(e)
    assert rig.poll.asked == ["run-1"]
    assert again.runs[0].run.state is RunState.RUNNING

    rig.clock.seconds = INTERVAL
    rig.observe(e)
    assert rig.poll.asked == ["run-1", "run-1"]


@pytest.mark.parametrize(
    "outcome",
    [RunOutcome.COMPLETED, RunOutcome.FAILED, RunOutcome.PAUSED, RunOutcome.ORPHANED],
)
def test_an_ended_outcome_is_finished_with_its_document(
    tmp_path: Path, outcome: RunOutcome
) -> None:
    doc = document("run-1", outcome)
    rig = Rig(tmp_path, doc)

    [observed] = rig.observe(entry()).runs

    assert observed.run.state is RunState.FINISHED
    assert observed.finished == RunEnded(doc)


def test_no_state_after_confirmation_is_a_vanished_run(tmp_path: Path) -> None:
    rig = Rig(tmp_path, document("run-1", RunOutcome.NOT_FOUND))

    [observed] = rig.observe(entry()).runs

    assert observed.run.state is RunState.FINISHED
    assert observed.finished == RunVanished()


@pytest.mark.parametrize(
    "answer",
    [
        document("run-1", RunOutcome.UNREADABLE),
        document("run-1", RunOutcome.UNKNOWN_STATUS),
        failure("sq timed out"),
    ],
    ids=["unreadable", "unknown_status", "poll_failure"],
)
def test_an_unusable_answer_is_a_fault_and_polling_continues(
    tmp_path: Path, answer: object
) -> None:
    rig = Rig(tmp_path, answer, document("run-1", RunOutcome.TIMED_OUT))  # type: ignore[arg-type]
    e = entry()

    [observed] = rig.observe(e).runs
    rig.clock.seconds = INTERVAL
    [later] = rig.observe(e).runs

    assert observed.run.state is RunState.FAULT
    assert observed.finished is None
    [fault] = [f for f in rig.faults if f.kind is FaultKind.RUN_OBSERVATION_FAILED]
    assert fault.run_id == "run-1" and fault.node_id == "node-1"
    assert later.run.state is RunState.RUNNING, "polling continued"


def test_runs_are_observed_least_recently_polled_first(tmp_path: Path) -> None:
    rig = Rig(
        tmp_path,
        *[document(f"run-{i}", RunOutcome.TIMED_OUT) for i in (2, 1, 2, 1)],
    )
    first, second = entry(1), entry(2)
    # Poll run 2 alone first, so run 1 has never been polled.
    rig.observe(second)
    rig.poll.asked.clear()

    rig.clock.seconds = INTERVAL
    rig.observe(second, first)

    assert rig.poll.asked == ["run-1", "run-2"]


def test_a_refused_budget_cuts_off_before_any_poll(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    rig.deadline = 0.0

    observed = rig.observe(entry())

    assert observed.result is TickResult.CUT_OFF
    assert rig.poll.asked == []


def test_the_budget_is_checked_before_every_poll(tmp_path: Path) -> None:
    rig = Rig(tmp_path, document("run-1", RunOutcome.TIMED_OUT))
    first, second = entry(1), entry(2)
    budgets = iter([True, False])

    class OneCall:
        def allows_call(self) -> bool:
            return next(budgets)

    observed = rig.observer.observe(
        (first, second),
        OneCall(),  # type: ignore[arg-type]
        rig.faults,
        rig.context,
        {},
    )

    assert rig.poll.asked == ["run-1"]
    assert observed.result is TickResult.CUT_OFF
    assert [r.run.run_id for r in observed.runs] == ["run-1"]


def test_a_confirmed_tracked_child_is_polled_like_any_run(tmp_path: Path) -> None:
    rig = Rig(tmp_path, document("run-1", RunOutcome.COMPLETED))
    e = entry()
    rig.launch(e, Child(0))
    rig.tracker.confirm(e.id)

    [observed] = rig.observe(e).runs

    assert observed.run.state is RunState.FINISHED


def test_the_node_in_context_is_the_entry_being_observed(tmp_path: Path) -> None:
    rig = Rig(tmp_path, document("run-1", RunOutcome.TIMED_OUT))

    rig.observe(entry(1))

    assert rig.context.node_id == "node-1"


def test_a_standing_poll_fault_recurs_between_polls(tmp_path: Path) -> None:
    rig = Rig(tmp_path, failure("sq timed out"))
    e = entry()
    rig.observe(e)

    rig.clock.seconds = 1.0
    [between] = rig.observe(e).runs

    assert rig.poll.asked == ["run-1"], "no extra poll"
    assert between.run.state is RunState.FAULT
    assert [f.kind for f in rig.faults] == [FaultKind.RUN_OBSERVATION_FAILED] * 2


def test_observing_one_projects_runs_keeps_anothers_poll_times(tmp_path: Path) -> None:
    """The observer is shared by every project: it must not prune by one list."""
    rig = Rig(
        tmp_path,
        document("run-1", RunOutcome.TIMED_OUT),
        document("run-2", RunOutcome.TIMED_OUT),
    )
    project_a, project_b = entry(1), entry(2)
    rig.observe(project_a)
    rig.observe(project_b)

    rig.clock.seconds = 1.0
    rig.observe(project_a)  # a tick of A only
    rig.observe(project_b)

    assert rig.poll.asked == ["run-1", "run-2"], "nothing was polled twice"


def test_a_malformed_run_id_faults_that_entry_and_the_others_are_still_observed(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path, document("run-2", RunOutcome.TIMED_OUT))
    bad = entry(1)
    bad = type(bad)(
        id=bad.id,
        project_id=bad.project_id,
        node_id=bad.node_id,
        kind=bad.kind,
        parameters={PARAM_PIPELINE: "p", PARAM_PARAMS: {}, PARAM_RUN_ID: ""},
        issued_at=bad.issued_at,
    )

    observed = rig.observe(bad, entry(2))

    assert [r.run.state for r in observed.runs] == [RunState.FAULT, RunState.RUNNING]
    assert observed.result is TickResult.COMPLETE
    [fault] = list(rig.faults)
    assert fault.kind is FaultKind.RUN_OBSERVATION_FAILED and "unusable" in fault.detail
