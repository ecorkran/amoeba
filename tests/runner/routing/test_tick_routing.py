"""Routing across ticks, holds and table edits, through the real tick (D8).

The tick, the planners, the store and the route stage are the production ones; the
run itself is the stub ``sq`` outcome of 125's rig, and launches start nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sq_stub_scripts import RunScript, single_review

from amoeba.process import RunOutcome
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.routing.recompute import recompute
from amoeba.runner.routing.table import RoutingTable
from amoeba.store import (
    CFReference,
    CommandKind,
    Node,
    NodeKind,
    NodeStatus,
    Route,
    RoutingDecision,
    Store,
)
from runner.dispatch.tick_rig import CF_PROJECT, DispatchRig
from runner.intent.intent_support import submit
from runner.routing.table_support import (
    ADVANCE_COMPLETED,
    TEST_AMOEBA_VERSION,
    shipped_table,
    small_table,
)

PROJECT = "demo"
SLICE = "routed"
INDEX = 125
#: What the pointer write renames the slice to: the stub CF's own slug for index 125.
CF_SLUG = "run-dispatch-and-outcome-ingestion"
PASS_VERDICT = "verdict: PASS"
STATED_CONCERNS = "verdict: CONCERNS"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    rig = DispatchRig(tmp_path, store)
    rig.tick_rig.routing_table = shipped_table()
    yield rig


def _launched(rig: DispatchRig) -> tuple[Node, Node]:
    """``(slice, step)``: a slice design step with its run in flight."""
    slice_node, step = rig.slice_and_step(SLICE, INDEX)
    rig.tick()
    rig.tick()
    assert rig.run_of(step)
    return slice_node, step


def _tasks_step(rig: DispatchRig, slice_node: Node) -> Node:
    """The successor of the slice design step."""
    return rig.store.create_node(
        project_id=PROJECT,
        kind=NodeKind.PHASE_OR_ARTIFACT,
        title=LifecycleStep.TASKS.value,
        parent_id=slice_node.id,
        cf=CFReference(project=CF_PROJECT, phase=LifecycleStep.TASKS.value),
    )


def _review(rig: DispatchRig, *, verdict: str, edit: str = "") -> RunScript:
    """The captured review, with its stated verdict set and (optionally) edited."""
    script = single_review(CF_SLUG)
    files = {
        path: text.replace(STATED_CONCERNS, verdict, 1) + edit
        for path, text in script.files.items()
    }
    for relative, text in files.items():
        target = rig.world.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return RunScript(files, script.document)


def _decisions(rig: DispatchRig, node: Node) -> list[RoutingDecision]:
    return rig.store.routing_decisions(node.id)


def test_advance_dispatches_successor_next_tick(rig: DispatchRig) -> None:
    slice_node, step = _launched(rig)
    tasks = _tasks_step(rig, slice_node)
    review = _review(rig, verdict=PASS_VERDICT)

    rig.end_run(step, RunOutcome.COMPLETED, **review.document)

    [decision] = _decisions(rig, step)
    assert decision.rule_id == "advance-on-stated-pass"
    assert rig.status(step) is NodeStatus.DONE, "routed in tick m"
    assert rig.entries(CommandKind.CF_WRITE, tasks) == [], "not dispatched in tick m"

    rig.tick()

    assert len(rig.entries(CommandKind.CF_WRITE, tasks)) == 1, "dispatched in tick m+1"


def test_rerun_relaunches_same_pipeline(rig: DispatchRig) -> None:
    _, step = _launched(rig)
    [first] = rig.entries(CommandKind.SQ_RUN, step)
    review = _review(rig, verdict=STATED_CONCERNS)

    rig.end_run(step, RunOutcome.COMPLETED, **review.document)

    [decision] = _decisions(rig, step)
    assert (decision.rule_id, decision.route) == ("rerun-new-concerns", Route.RERUN)
    assert rig.status(step) is NodeStatus.RUNNABLE
    rig.tick()
    rig.tick()

    runs = rig.entries(CommandKind.SQ_RUN, step)
    assert len(runs) == 2
    second = runs[-1]
    assert second.id != first.id
    assert second.parameters[PARAM_PIPELINE] == first.parameters[PARAM_PIPELINE]
    assert second.parameters[PARAM_PARAMS] == first.parameters[PARAM_PARAMS]


def test_held_step_outcome_is_routed(rig: DispatchRig) -> None:
    slice_node, step = _launched(rig)
    tasks = _tasks_step(rig, slice_node)
    submit(rig.store, {"intent": "pause"}, project_id=PROJECT)
    review = _review(rig, verdict=PASS_VERDICT)

    rig.end_run(step, RunOutcome.COMPLETED, **review.document)
    rig.tick()
    rig.tick()

    [decision] = _decisions(rig, step)
    assert decision.route is Route.ADVANCE, "a held step's outcome is still routed"
    assert rig.status(step) is NodeStatus.DONE
    assert rig.entries(CommandKind.CF_WRITE, tasks) == [], "nothing new under a hold"
    assert rig.entries(CommandKind.SQ_RUN, tasks) == []


def _edited(rules: str) -> RoutingTable:
    return small_table(rules)


def test_decisions_recompute_against_their_own_table_version(
    rig: DispatchRig,
) -> None:
    table_a = shipped_table()
    _, step = _launched(rig)
    rig.end_run(
        step,
        RunOutcome.COMPLETED,
        **_review(rig, verdict=STATED_CONCERNS).document,
    )
    rig.tick()
    rig.tick()
    assert len(rig.entries(CommandKind.SQ_RUN, step)) == 2

    # The restart: a table edited to have no rerun rule, so a second round of the
    # same concerns takes the first rule that still applies.
    table_b = _edited(ADVANCE_COMPLETED)
    rig.tick_rig.routing_table = table_b
    assert table_b.version != table_a.version
    rig.end_run(
        step,
        RunOutcome.COMPLETED,
        **_review(rig, verdict=STATED_CONCERNS, edit="\nOne more line.\n").document,
    )

    first, second = _decisions(rig, step)
    assert (first.table_version, second.table_version) == (
        table_a.version,
        table_b.version,
    )
    assert (first.rule_id, second.rule_id) == (
        "rerun-new-concerns",
        "advance-completed",
    )
    stored_a = rig.store.routing_table_version(table_a.version)
    stored_b = rig.store.routing_table_version(table_b.version)
    assert stored_a is not None and stored_b is not None
    assert recompute(first, stored_a).matches is True
    assert recompute(second, stored_b).matches is True
    # Each only against its own version: the first decision is not table B's.
    assert recompute(first, stored_b).matches is False
    assert first.amoeba_version == second.amoeba_version == TEST_AMOEBA_VERSION
