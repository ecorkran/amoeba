"""One project's tick against a real store, a test planner and a fake Popen."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from amoeba.process import RunOutcome, UpstreamShapeError
from amoeba.runner.budget import TickResult
from amoeba.runner.faults import FaultKind
from amoeba.runner.launch import (
    log_paths,
)
from amoeba.store import (
    PARAM_RUN_ID,
    CommandKind,
    JournalOutcome,
    Node,
    NodeKind,
    Store,
)
from runner.observe_support import (
    Child,
    document,
)
from runner.tick_support import (
    PROJECT,
    Rig,
    drive_project,
    ready_step,
    runnable_unbusy,
)


@pytest.fixture
def node(store: Store) -> Node:
    step = ready_step(store)
    drive_project(store)
    return step


def test_the_entry_is_journaled_before_the_launch_call(
    tmp_path: Path, store: Store, node: Node
) -> None:
    rig = Rig(tmp_path, store)

    result, tick = rig.tick()

    assert result is TickResult.COMPLETE and tick.wrote
    assert rig.popen.open_entries_at_call == [1]
    [entry] = store.unresolved_journal_entries(PROJECT)
    assert entry.node_id == node.id and entry.kind is CommandKind.SQ_RUN
    assert entry.parameters["pipeline"] == "P4"
    assert entry.parameters["params"] == {"k": "v"}
    assert entry.parameters["checkout"] == str(tmp_path)
    assert str(entry.parameters[PARAM_RUN_ID]).startswith("amoeba-")
    assert rig.tracker.get(entry.id) is not None


def test_a_node_with_an_unresolved_entry_is_not_offered_to_decide(
    tmp_path: Path, store: Store, node: Node
) -> None:
    rig = Rig(tmp_path, store, document("x", RunOutcome.TIMED_OUT))
    rig.tick()
    rig.planner.views.clear()

    rig.clock.seconds = 1.0
    rig.tick()

    [view] = rig.planner.views
    assert runnable_unbusy(view) == []
    assert len(view.in_flight) == 1
    assert rig.popen.calls == 1, "not launched twice"


def test_a_failed_launch_is_recorded_through_finish(
    tmp_path: Path, store: Store, node: Node
) -> None:
    rig = Rig(tmp_path, store)
    rig.popen.error = FileNotFoundError("sq")

    result, _ = rig.tick()

    assert result is TickResult.COMPLETE
    [entry] = store.journal_entries(PROJECT)
    assert entry.outcome is JournalOutcome.FAILED
    assert entry.result is not None
    assert entry.result["launch_failure"] == "spawn_error"
    assert store.blocked_state_for(node.id) is not None


def test_a_finished_run_is_recorded_and_its_handle_forgotten(
    tmp_path: Path, store: Store, node: Node
) -> None:
    rig = Rig(tmp_path, store)
    rig.tick()
    [entry] = store.unresolved_journal_entries(PROJECT)
    run_id = str(entry.parameters[PARAM_RUN_ID])
    log_paths(rig.supervisor_dir, entry.id).stderr.write_text(f"run_id={run_id}\n")
    rig.poll.answers.append(document(run_id, RunOutcome.COMPLETED))
    rig.clock.seconds = 1.0
    rig.tick()  # the line confirms the launch; no poll yet

    rig.clock.seconds = 20.0
    result, tick = rig.tick()

    assert result is TickResult.COMPLETE and tick.wrote
    resolved = store.journal_entry(entry.id)
    assert resolved is not None and resolved.outcome is JournalOutcome.COMPLETED
    assert rig.tracker.get(entry.id) is None


def test_a_tick_that_only_polled_a_running_run_wrote_nothing(
    tmp_path: Path, store: Store, node: Node
) -> None:
    rig = Rig(tmp_path, store)
    rig.tick()
    [entry] = store.unresolved_journal_entries(PROJECT)
    run_id = str(entry.parameters[PARAM_RUN_ID])
    rig.tracker.confirm(entry.id)
    rig.poll.answers.append(document(run_id, RunOutcome.TIMED_OUT))

    result, tick = rig.tick()

    assert result is TickResult.COMPLETE
    assert rig.poll.asked == [run_id]
    assert not tick.wrote


def test_exit_two_with_no_state_records_the_failure_then_raises_upstream_shape(
    tmp_path: Path, store: Store, node: Node
) -> None:
    rig = Rig(tmp_path, store)
    rig.tick()
    [entry] = store.unresolved_journal_entries(PROJECT)
    rig.tracker.track(entry.id, Child(2))  # replaces the live child
    rig.poll.answers.append(
        document(str(entry.parameters[PARAM_RUN_ID]), RunOutcome.NOT_FOUND)
    )

    with pytest.raises(UpstreamShapeError, match="--run-id"):
        rig.tick()

    resolved = store.journal_entry(entry.id)
    assert resolved is not None and resolved.outcome is JournalOutcome.FAILED


def test_complete_closes_a_non_recurring_escalation(
    tmp_path: Path, store: Store
) -> None:
    store.raise_project_escalation(
        PROJECT, fault_kind=FaultKind.CF_PROBE_FAILED.value, payload={"detail": "x"}
    )
    rig = Rig(tmp_path, store)

    result, tick = rig.tick()

    assert result is TickResult.COMPLETE and tick.wrote
    assert store.open_project_escalations(PROJECT) == []


def test_a_recurring_fault_keeps_its_escalation_open_and_writes_one_row(
    tmp_path: Path, store: Store, node: Node
) -> None:
    rig = Rig(tmp_path, store)
    rig.tick()
    [entry] = store.unresolved_journal_entries(PROJECT)
    rig.tracker.confirm(entry.id)
    rig.poll.answers.append(document("x", RunOutcome.UNKNOWN_STATUS))

    rig.clock.seconds = 20.0
    rig.tick()
    rig.poll.answers.append(document("x", RunOutcome.UNKNOWN_STATUS))
    rig.clock.seconds = 40.0
    rig.tick()

    [open_row] = store.open_project_escalations(PROJECT)
    assert open_row.fault_kind == FaultKind.RUN_OBSERVATION_FAILED.value


def test_a_cut_off_tick_closes_nothing(
    tmp_path: Path, store: Store, node: Node
) -> None:
    rig = Rig(tmp_path, store)
    rig.tick()
    store.raise_project_escalation(
        PROJECT, fault_kind=FaultKind.CF_PROBE_FAILED.value, payload={"detail": "x"}
    )
    [entry] = store.unresolved_journal_entries(PROJECT)
    rig.tracker.confirm(entry.id)
    rig.deadline = 0.0

    result, _ = rig.tick()

    assert result is TickResult.CUT_OFF
    assert len(store.open_project_escalations(PROJECT)) == 1


def test_the_budget_is_checked_before_popen(
    tmp_path: Path, store: Store, node: Node
) -> None:
    rig = Rig(tmp_path, store)
    rig.deadline = 0.0

    result, _ = rig.tick()

    assert result is TickResult.CUT_OFF
    assert rig.popen.calls == 0
    assert store.journal_entries(PROJECT) == []


def test_the_node_in_context_is_the_node_being_launched(
    tmp_path: Path, store: Store, node: Node
) -> None:
    rig = Rig(tmp_path, store)
    seen: list[str | None] = []
    original = rig.popen.__call__

    def spy(argv: list[str], **kwargs: Any) -> Child:
        seen.append(rig.context.node_id)
        return original(argv, **kwargs)

    rig.popen = spy  # type: ignore[assignment]

    rig.tick()

    assert seen == [node.id]


def test_the_view_tree_holds_every_node_of_the_project(
    tmp_path: Path, store: Store, node: Node
) -> None:
    other = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="m")
    store.create_node(project_id="elsewhere", kind=NodeKind.SLICE, title="x")
    parent_id = node.parent_id
    rig = Rig(tmp_path, store)

    rig.tick()

    [view] = rig.planner.views
    assert parent_id is not None
    assert {n.id for n in view.tree.nodes} == {parent_id, node.id, other.id}
