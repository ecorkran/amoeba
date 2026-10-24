"""Hold through the tick: a pause stops planning, however the rows combine (D7)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.runner.decide import Action, BlockHumanStep, ProjectView
from amoeba.runner.factory import PRODUCTION_PLANNERS
from amoeba.runner.lifecycle.human_steps import HumanStepPlanner
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import Channel, Node, NodeStatus
from runner.lifecycle.tree_support import TreeBuilder
from runner.tick_support import PROJECT, Rig, StoreHost, tenant_for

from .intent.intent_support import submit


class Everything:
    """A faulty planner: acts on every ready step, current or not."""

    def plan(self, view: ProjectView) -> list[Action]:
        return [BlockHumanStep(n.id) for n in view.tree.ready_steps()]


@pytest.fixture
def builder() -> Iterator[TreeBuilder]:
    built = TreeBuilder()
    yield built
    built.close()


def _ready_merge(builder: TreeBuilder) -> tuple[Node, Node]:
    """A slice whose human ``merge`` step is ready. Returns the slice and the step."""
    initiative = builder.initiative(140)
    sliced = builder.slice(initiative, 141)
    for step in (LifecycleStep.ARCHITECTURE, LifecycleStep.SLICE_PLAN):
        builder.done(builder.step_node(initiative, step))
    for step in (
        LifecycleStep.SLICE_DESIGN,
        LifecycleStep.TASKS,
        LifecycleStep.IMPLEMENTATION,
    ):
        builder.done(builder.step_node(sliced, step))
    return sliced, builder.step_node(sliced, LifecycleStep.MERGE)


def _status(builder: TreeBuilder, node: Node) -> NodeStatus:
    return builder.fresh(node).status


def _rig(tmp_path: Path, builder: TreeBuilder, *planners: object) -> Rig:
    rig = Rig(tmp_path, builder.store)
    rig.planners = planners
    return rig


def test_project_pause_wins_over_slice_resume(
    tmp_path: Path, builder: TreeBuilder
) -> None:
    sliced, merge = _ready_merge(builder)
    rig = _rig(tmp_path, builder, HumanStepPlanner())
    store = builder.store
    for body in ({"intent": "drive"}, {"intent": "pause"}):
        submit(store, body)
    for body in ({"intent": "resume"}, {"intent": "drive"}):
        submit(store, body, node_id=sliced.id)

    rig.tick()
    assert _status(builder, merge) is NodeStatus.RUNNABLE, "the project pause holds it"

    submit(store, {"intent": "resume"})
    rig.tick()
    assert _status(builder, merge) is NodeStatus.BLOCKED_ON_HUMAN


def test_a_planner_that_acts_on_a_held_step_faults_the_project_once(
    tmp_path: Path, builder: TreeBuilder
) -> None:
    _, merge = _ready_merge(builder)
    rig = _rig(tmp_path, builder, Everything())
    store = builder.store
    submit(store, {"intent": "drive"})
    submit(store, {"intent": "pause"})
    tenant = tenant_for(rig)

    for _ in range(2):
        tenant.tick(StoreHost(store))

    assert [m.fault_kind for m in store.open_project_escalations(PROJECT)] == [
        "unexpected_fault"
    ]
    assert len(store.messages(PROJECT, channel=Channel.ESCALATION)) == 1
    assert _status(builder, merge) is NodeStatus.RUNNABLE


def test_the_production_tuple_blocks_nothing_under_a_held_human_step(
    tmp_path: Path, builder: TreeBuilder
) -> None:
    _, merge = _ready_merge(builder)
    rig = _rig(tmp_path, builder, *PRODUCTION_PLANNERS)
    submit(builder.store, {"intent": "drive"})
    submit(builder.store, {"intent": "pause"})

    rig.tick()
    rig.tick()

    assert _status(builder, merge) is NodeStatus.RUNNABLE
    assert builder.store.messages(PROJECT, channel=Channel.ESCALATION) == []
