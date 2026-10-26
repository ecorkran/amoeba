"""Hold through the tick: a pause stops planning, however the rows combine (D7)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.process import RunOutcome
from amoeba.runner.decide import Action, BlockHumanStep, ProjectView
from amoeba.runner.factory import PRODUCTION_PLANNERS
from amoeba.runner.lifecycle.human_steps import HumanStepPlanner
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import (
    BLOCKED_STATUSES,
    PARAM_RUN_ID,
    BlockedKind,
    Channel,
    Node,
    NodeStatus,
    Store,
)
from runner.lifecycle.tree_support import TreeBuilder
from runner.observe_support import document
from runner.plan_tick_support import serve_plan
from runner.tick_support import (
    PLAN_READ_INTERVAL,
    PROJECT,
    Rig,
    StoreHost,
    drive_project,
    link,
    ready_step,
    tenant_for,
)

from .intent.intent_support import submit

pytestmark = pytest.mark.usefixtures("passing_checks")


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


def test_a_run_under_a_held_step_is_still_polled_and_a_block_stays(
    tmp_path: Path, store: Store
) -> None:
    step = ready_step(store)
    drive_project(store)
    rig = Rig(tmp_path, store)
    rig.tick()  # launches the step's run
    [entry] = store.unresolved_journal_entries(PROJECT)
    run_id = str(entry.parameters[PARAM_RUN_ID])
    rig.tracker.confirm(entry.id)
    rig.poll.answers.append(document(run_id, RunOutcome.TIMED_OUT))
    waiting = ready_step(store)
    store.block(waiting.id, kind=BlockedKind.HUMAN, context="blocked before the hold")

    submit(store, {"intent": "pause"})
    rig.clock.seconds += PLAN_READ_INTERVAL
    rig.tick()

    assert rig.poll.asked == [run_id]
    assert [e.id for e in store.unresolved_journal_entries(PROJECT)] == [entry.id]
    stored = store.get_node(waiting.id)
    assert stored is not None and stored.status is NodeStatus.BLOCKED_ON_HUMAN
    assert step.id == entry.node_id


def test_linking_a_project_escalates_nothing(tmp_path: Path, store: Store) -> None:
    rig = Rig(tmp_path, store)
    rig.planners = PRODUCTION_PLANNERS
    link(store, "s-1", "cf-1", PROJECT)
    serve_plan(rig.cf, (100,), {100: (101,)})

    rig.tick()
    rig.clock.seconds += PLAN_READ_INTERVAL
    rig.tick()

    assert store.messages(PROJECT, channel=Channel.ESCALATION) == []
    nodes = store.nodes_for_project(PROJECT)
    assert not [n for n in nodes if n.status in BLOCKED_STATUSES]
    assert nodes, "the plan was read and the tree built"
