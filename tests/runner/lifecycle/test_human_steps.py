"""``HumanStepPlanner``: a ready human step, and nothing else, is blocked."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from amoeba.runner.decide import BlockHumanStep, ProjectView, decide
from amoeba.runner.gates.merge_observation import (
    Merged,
    MergeObservation,
    NotMerged,
    Unobservable,
)
from amoeba.runner.lifecycle.human_steps import HumanStepPlanner
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import DesiredState
from runner.intent.rows_support import row
from runner.tick_support import view_for

from .tree_support import TreeBuilder

NOW = datetime(2026, 10, 23, tzinfo=UTC)


@pytest.fixture
def builder() -> Iterator[TreeBuilder]:
    built = TreeBuilder()
    yield built
    built.close()


DRIVEN = (row(drive=True),)


def _plan(builder: TreeBuilder, rows: tuple[DesiredState, ...] = DRIVEN) -> list[str]:
    view = view_for(builder.tree(), rows)
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


def _ready_merge(builder: TreeBuilder) -> str:
    """The id of a merge step that is current: its implementation is done."""
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
    return builder.step_node(slice_node, LifecycleStep.MERGE).id


def _merge_plan(
    builder: TreeBuilder, observations: dict[str, MergeObservation]
) -> list[BlockHumanStep]:
    view = replace(view_for(builder.tree(), DRIVEN), merge_observations=observations)
    return [a for a in HumanStepPlanner().plan(view) if isinstance(a, BlockHumanStep)]


def test_merge_is_blocked_while_git_shows_it_is_not_merged(
    builder: TreeBuilder,
) -> None:
    merge_id = _ready_merge(builder)

    assert _merge_plan(builder, {merge_id: NotMerged()}) == [BlockHumanStep(merge_id)]


def test_an_unobservable_merge_is_blocked_with_the_reason(
    builder: TreeBuilder,
) -> None:
    merge_id = _ready_merge(builder)

    [action] = _merge_plan(builder, {merge_id: Unobservable("ended on the target")})

    assert action.node_id == merge_id
    assert action.payload_extra == {
        "merge_observation": "unobservable",
        "reason": "ended on the target",
    }


def test_a_merge_with_no_observation_this_tick_is_skipped(
    builder: TreeBuilder,
) -> None:
    _ready_merge(builder)

    assert _merge_plan(builder, {}) == []


def test_a_merge_git_shows_done_is_not_blocked(builder: TreeBuilder) -> None:
    merge_id = _ready_merge(builder)

    assert _merge_plan(builder, {merge_id: Merged("abc")}) == []


def test_a_step_under_an_orphan_or_already_blocked_gets_no_action(
    builder: TreeBuilder,
) -> None:
    orphaned = builder.initiative(100)
    blocked = builder.initiative(200)
    builder.orphan(orphaned)
    builder.block(builder.step_node(blocked, LifecycleStep.ARCHITECTURE))

    assert _plan(builder) == []


def test_two_actions_for_one_node_are_still_refused(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    node_id = builder.step_node(initiative, LifecycleStep.ARCHITECTURE).id
    view = view_for(builder.tree(), DRIVEN)

    class Twice:
        def plan(self, view: ProjectView) -> list[BlockHumanStep]:
            return [BlockHumanStep(node_id)]

    with pytest.raises(ValueError, match="more than one action"):
        decide(view, [Twice(), Twice()])


def test_nothing_is_planned_when_nothing_is_driven(builder: TreeBuilder) -> None:
    builder.initiative(100)
    assert _plan(builder, ()) == []


def test_nothing_is_planned_when_the_project_is_paused(builder: TreeBuilder) -> None:
    builder.initiative(100)
    assert _plan(builder, (row(drive=True, hold=True),)) == []


def test_a_step_already_blocked_on_a_human_is_not_blocked_again(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    builder.block(builder.step_node(initiative, LifecycleStep.ARCHITECTURE))
    assert _plan(builder) == []
