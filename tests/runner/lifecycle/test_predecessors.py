"""``predecessors`` and ``predecessors_done``: one test per row of D4's table."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from amoeba.runner.lifecycle.predecessors import predecessors, predecessors_done
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store.models import Node

from .tree_support import TreeBuilder

ARCHITECTURE = LifecycleStep.ARCHITECTURE
SLICE_PLAN = LifecycleStep.SLICE_PLAN
SLICE_DESIGN = LifecycleStep.SLICE_DESIGN
TASKS = LifecycleStep.TASKS
IMPLEMENTATION = LifecycleStep.IMPLEMENTATION
MERGE = LifecycleStep.MERGE
INTEGRATION = LifecycleStep.INTEGRATION


@pytest.fixture
def builder() -> Iterator[TreeBuilder]:
    built = TreeBuilder()
    yield built
    built.close()


def _waits_for(builder: TreeBuilder, node: Node) -> set[str]:
    """The ``parent title: step`` labels of the node's predecessors."""
    tree = builder.tree()
    labels: set[str] = set()
    for found in predecessors(tree, node):
        parent = tree.parent(found)
        step = tree.step_of(found)
        assert parent is not None and step is not None
        labels.add(f"{parent.title}: {step.value}")
    return labels


def test_architecture_waits_for_nothing(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    step = builder.step_node(initiative, ARCHITECTURE)

    assert predecessors(builder.tree(), step) == ()
    assert predecessors_done(builder.tree(), step)


def test_slice_plan_waits_for_architecture(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    step = builder.step_node(initiative, SLICE_PLAN)

    assert _waits_for(builder, step) == {"initiative 100: architecture"}


def test_slice_design_waits_for_the_initiatives_slice_plan(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    step = builder.step_node(builder.slice(initiative, 101), SLICE_DESIGN)

    assert _waits_for(builder, step) == {"initiative 100: slice_plan"}


def test_tasks_waits_for_slice_design(builder: TreeBuilder) -> None:
    slice_node = builder.slice(builder.initiative(100), 101)

    step = builder.step_node(slice_node, TASKS)

    assert _waits_for(builder, step) == {"slice 101: slice_design"}


def test_the_first_slices_implementation_waits_only_for_tasks(
    builder: TreeBuilder,
) -> None:
    slice_node = builder.slice(builder.initiative(100), 101)

    step = builder.step_node(slice_node, IMPLEMENTATION)

    assert _waits_for(builder, step) == {"slice 101: tasks"}


def test_a_later_slices_implementation_waits_for_the_previous_merge(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    builder.slice(initiative, 101)
    second = builder.slice(initiative, 102)

    step = builder.step_node(second, IMPLEMENTATION)

    assert _waits_for(builder, step) == {"slice 102: tasks", "slice 101: merge"}


def test_merge_waits_for_implementation(builder: TreeBuilder) -> None:
    slice_node = builder.slice(builder.initiative(100), 101)

    step = builder.step_node(slice_node, MERGE)

    assert _waits_for(builder, step) == {"slice 101: implementation"}


def test_integration_waits_for_slice_plan_and_every_eligible_merge(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    builder.slice(initiative, 101)
    builder.slice(initiative, 102)

    step = builder.step_node(initiative, INTEGRATION)

    assert _waits_for(builder, step) == {
        "initiative 100: slice_plan",
        "slice 101: merge",
        "slice 102: merge",
    }


# -- the corners of "previous" and "eligible" ----------------------------------


def test_the_next_slices_design_does_not_wait_for_the_previous_slice(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    builder.slice(initiative, 101)
    second = builder.slice(initiative, 102)

    step = builder.step_node(second, SLICE_DESIGN)

    assert _waits_for(builder, step) == {"initiative 100: slice_plan"}


def test_an_orphaned_slice_and_a_stepless_slice_are_not_previous(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    orphan = builder.slice(initiative, 101)
    builder.slice(initiative, 102, with_steps=False)
    last = builder.slice(initiative, 103)
    builder.orphan(orphan)

    step = builder.step_node(last, IMPLEMENTATION)

    assert _waits_for(builder, step) == {"slice 103: tasks"}


def test_previous_follows_cf_index_not_creation_order(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    builder.slice(initiative, 105)
    builder.slice(initiative, 101)
    middle = builder.slice(initiative, 103)

    step = builder.step_node(middle, IMPLEMENTATION)

    assert _waits_for(builder, step) == {"slice 103: tasks", "slice 101: merge"}


def test_a_slice_with_steps_holds_the_next_implementation_until_its_merge(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    held = builder.slice(initiative, 101)
    second = builder.slice(initiative, 102)
    step = builder.step_node(second, IMPLEMENTATION)
    builder.done(builder.step_node(second, TASKS))

    assert not predecessors_done(builder.tree(), step)
    builder.done(builder.step_node(held, MERGE))
    assert predecessors_done(builder.tree(), step)


def test_integration_skips_ineligible_slices(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    builder.slice(initiative, 101, with_steps=False)
    builder.slice(initiative, 102)

    step = builder.step_node(initiative, INTEGRATION)

    assert _waits_for(builder, step) == {
        "initiative 100: slice_plan",
        "slice 102: merge",
    }


# -- done-ness -----------------------------------------------------------------


def test_predecessors_done_follows_the_status_of_each_predecessor(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    plan = builder.step_node(initiative, SLICE_PLAN)
    assert not predecessors_done(builder.tree(), plan)

    builder.done(builder.step_node(initiative, ARCHITECTURE))

    assert predecessors_done(builder.tree(), plan)


def test_a_missing_predecessor_step_is_not_done(builder: TreeBuilder) -> None:
    partial = builder.slice(builder.initiative(100), 101, with_steps=False)
    tasks = builder.step(partial, TASKS)

    tree = builder.tree()

    assert predecessors(tree, tasks) == ()
    assert not predecessors_done(tree, tasks)


def test_a_non_step_node_is_refused(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)

    with pytest.raises(ValueError, match="not a step"):
        predecessors(builder.tree(), initiative)
