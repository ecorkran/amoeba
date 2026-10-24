"""``HumanStepPlanner``: a ready human step, and nothing else, is blocked."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from amoeba.runner.decide import BlockHumanStep, ProjectView, decide
from amoeba.runner.factory import PRODUCTION_PLANNERS
from amoeba.runner.lifecycle.human_steps import HumanStepPlanner
from amoeba.runner.lifecycle.steps import LifecycleStep
from runner.tick_support import view_for

from .tree_support import TreeBuilder

NOW = datetime(2026, 10, 23, tzinfo=UTC)


@pytest.fixture
def builder() -> Iterator[TreeBuilder]:
    built = TreeBuilder()
    yield built
    built.close()


def _plan(builder: TreeBuilder) -> list[str]:
    view = view_for(builder.tree())
    return [
        a.node_id
        for a in HumanStepPlanner().plan(view)
        if isinstance(a, BlockHumanStep)
    ]


def test_a_ready_human_step_gets_a_block_action(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    architecture = builder.step_node(initiative, LifecycleStep.ARCHITECTURE)

    assert _plan(builder) == [architecture.id]


def test_a_pipeline_step_gets_none(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    builder.done(builder.step_node(initiative, LifecycleStep.ARCHITECTURE))
    builder.done(builder.step_node(initiative, LifecycleStep.SLICE_PLAN))
    builder.slice(initiative, 101)

    assert _plan(builder) == [], "slice_design is ready, but it is a pipeline step"


def test_merge_is_blocked_once_implementation_is_done(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    builder.done(builder.step_node(initiative, LifecycleStep.ARCHITECTURE))
    builder.done(builder.step_node(initiative, LifecycleStep.SLICE_PLAN))
    slice_node = builder.slice(initiative, 101)
    for step in (
        LifecycleStep.SLICE_DESIGN,
        LifecycleStep.TASKS,
        LifecycleStep.IMPLEMENTATION,
    ):
        builder.done(builder.step_node(slice_node, step))

    assert _plan(builder) == [builder.step_node(slice_node, LifecycleStep.MERGE).id]


def test_a_step_under_an_orphan_or_already_blocked_gets_no_action(
    builder: TreeBuilder,
) -> None:
    orphaned = builder.initiative(100)
    blocked = builder.initiative(200)
    builder.orphan(orphaned)
    builder.block(builder.step_node(blocked, LifecycleStep.ARCHITECTURE))

    assert _plan(builder) == []


def test_two_actions_for_one_node_are_still_refused(builder: TreeBuilder) -> None:
    view = view_for(builder.tree())

    class Twice:
        def plan(self, view: ProjectView) -> list[BlockHumanStep]:
            return [BlockHumanStep("n-1")]

    with pytest.raises(ValueError, match="more than one action"):
        decide(view, [Twice(), Twice()])


def test_the_production_planner_tuple_is_empty() -> None:
    assert PRODUCTION_PLANNERS == ()
