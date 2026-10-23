"""Observation of a launch that is not yet confirmed (D6)."""

from __future__ import annotations

from pathlib import Path

from amoeba.process import RunOutcome
from amoeba.runner.budget import TickResult
from amoeba.runner.decide import RunState
from amoeba.runner.faults import FaultKind, LaunchFailure
from amoeba.runner.launch import log_paths
from amoeba.runner.observed import LaunchFailed, RunEnded
from runner.observe_support import (
    GRACE,
    INTERVAL,
    Child,
    Rig,
    document,
    entry,
    failure,
)

LINE = "run_id=run-1\n"


def test_the_exact_line_confirms_without_a_poll(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    e = entry()
    rig.launch(e, Child(None), stderr="banner\n" + LINE)

    [observed] = rig.observe(e).runs

    assert observed.run.state is RunState.RUNNING
    assert rig.poll.asked == []
    tracked = rig.tracker.get(e.id)
    assert tracked is not None and tracked.confirmed


def test_an_unconfirmed_launch_inside_grace_is_launching_and_not_polled(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path)
    e = entry(issued_ago=5)
    rig.launch(e, Child(None))

    for seconds in (0.0, INTERVAL, INTERVAL * 2):
        rig.clock.seconds = seconds
        [observed] = rig.observe(e).runs
        assert observed.run.state is RunState.LAUNCHING

    assert rig.poll.asked == []
    assert len(rig.faults) == 0


def test_a_poll_finding_a_state_confirms_when_the_grace_passes(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path, document("run-1", RunOutcome.TIMED_OUT))
    e = entry(issued_ago=GRACE + 1)
    rig.launch(e, Child(None))

    [observed] = rig.observe(e).runs

    assert rig.poll.asked == ["run-1"]
    assert observed.run.state is RunState.RUNNING
    tracked = rig.tracker.get(e.id)
    assert tracked is not None and tracked.confirmed


def test_overdue_keeps_the_entry_and_raises_launch_overdue(tmp_path: Path) -> None:
    rig = Rig(tmp_path, document("run-1", RunOutcome.NOT_FOUND))
    e = entry(issued_ago=GRACE + 1)
    rig.launch(e, Child(None), stderr="still starting\n")

    [observed] = rig.observe(e).runs

    assert observed.run.state is RunState.LAUNCHING
    assert observed.finished is None
    [fault] = list(rig.faults)
    assert fault.kind is FaultKind.LAUNCH_OVERDUE
    assert "still starting" in fault.detail and "run-1" in fault.detail


def test_overdue_recurs_each_tick_and_polls_on_the_run_interval(
    tmp_path: Path,
) -> None:
    rig = Rig(
        tmp_path,
        document("run-1", RunOutcome.NOT_FOUND),
        document("run-1", RunOutcome.NOT_FOUND),
    )
    e = entry(issued_ago=GRACE + 1)
    rig.launch(e, Child(None))
    rig.observe(e)

    rig.clock.seconds = 1.0
    rig.observe(e)
    assert rig.poll.asked == ["run-1"], "not polled again inside the interval"

    rig.clock.seconds = INTERVAL
    rig.observe(e)
    assert rig.poll.asked == ["run-1", "run-1"]
    assert [f.kind for f in rig.faults] == [FaultKind.LAUNCH_OVERDUE] * 3


def test_an_overdue_launch_is_confirmed_by_a_late_line(tmp_path: Path) -> None:
    rig = Rig(tmp_path, document("run-1", RunOutcome.NOT_FOUND))
    e = entry(issued_ago=GRACE + 1)
    rig.launch(e, Child(None))
    rig.observe(e)

    log_paths(rig.supervisor_dir, e.id).stderr.write_text(LINE)
    rig.clock.seconds = 1.0
    [observed] = rig.observe(e).runs

    assert observed.run.state is RunState.RUNNING
    assert len(rig.faults) == 1, "no further overdue fault once confirmed"


def test_an_exit_without_the_line_or_a_state_is_a_failed_launch(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path, document("run-1", RunOutcome.NOT_FOUND))
    e = entry(issued_ago=1)
    rig.launch(e, Child(1), stderr="boom: provider unreachable\n")

    [observed] = rig.observe(e).runs

    assert observed.run.state is RunState.FINISHED
    assert observed.finished == LaunchFailed(
        LaunchFailure.EXITED_BEFORE_LINE, 1, "boom: provider unreachable\n"
    )


def test_an_exit_with_a_state_observes_the_run_instead(tmp_path: Path) -> None:
    doc = document("run-1", RunOutcome.COMPLETED)
    rig = Rig(tmp_path, doc)
    e = entry(issued_ago=1)
    rig.launch(e, Child(0))

    [observed] = rig.observe(e).runs

    assert observed.finished == RunEnded(doc)


def test_exit_two_without_a_state_is_a_usage_error(tmp_path: Path) -> None:
    rig = Rig(tmp_path, document("run-1", RunOutcome.NOT_FOUND))
    e = entry(issued_ago=1)
    rig.launch(e, Child(2), stderr="no such option: --run-id\n")

    [observed] = rig.observe(e).runs

    assert isinstance(observed.finished, LaunchFailed)
    assert observed.finished.failure is LaunchFailure.USAGE_ERROR
    assert observed.finished.exit_code == 2


def test_an_unreadable_log_answers_no_line_and_the_state_decides(
    tmp_path: Path,
) -> None:
    doc = document("run-1", RunOutcome.TIMED_OUT)
    rig = Rig(tmp_path, doc)
    e = entry(issued_ago=GRACE + 1)
    rig.tracker.track(e.id, Child(None))  # no log file exists

    [observed] = rig.observe(e).runs

    assert observed.run.state is RunState.RUNNING, "the poll found a state"
    [fault] = list(rig.faults)
    assert fault.kind is FaultKind.RUN_OBSERVATION_FAILED
    assert e.id in fault.detail and "unreadable" in fault.detail


def test_the_error_replaces_the_tail_when_the_log_is_unreadable(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path, document("run-1", RunOutcome.NOT_FOUND))
    e = entry(issued_ago=1)
    rig.tracker.track(e.id, Child(1))  # no log file exists

    [observed] = rig.observe(e).runs

    assert isinstance(observed.finished, LaunchFailed)
    assert observed.finished.tail.startswith("stderr log unreadable")


def test_a_failed_poll_after_an_exit_is_a_fault_and_the_entry_stays(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path, failure("sq timed out"))
    e = entry(issued_ago=1)
    rig.launch(e, Child(1))

    [observed] = rig.observe(e).runs

    assert observed.run.state is RunState.FAULT
    assert observed.finished is None


def test_the_budget_is_checked_before_the_launch_poll(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    rig.deadline = 0.0
    e = entry(issued_ago=GRACE + 1)
    rig.launch(e, Child(None))

    observed = rig.observe(e)

    assert observed.result is TickResult.CUT_OFF
    assert rig.poll.asked == []
