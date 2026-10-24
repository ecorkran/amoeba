"""``LifecycleTree.ready_steps``: runnable, linked, unblocked, predecessors done."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store.models import Node

from .tree_support import TreeBuilder

ARCHITECTURE = LifecycleStep.ARCHITECTURE
SLICE_PLAN = LifecycleStep.SLICE_PLAN
SLICE_DESIGN = LifecycleStep.SLICE_DESIGN
TASKS = LifecycleStep.TASKS
IMPLEMENTATION = LifecycleStep.IMPLEMENTATION
MERGE = LifecycleStep.MERGE


@pytest.fixture
def builder() -> Iterator[TreeBuilder]:
    built = TreeBuilder()
    yield built
    built.close()


def _ready(builder: TreeBuilder) -> set[str]:
    """``owner title: step`` labels of the ready steps."""
    tree = builder.tree()
    labels: set[str] = set()
    for node in tree.ready_steps():
        owner, step = tree.parent(node), tree.step_of(node)
        assert owner is not None and step is not None
        labels.add(f"{owner.title}: {step.value}")
    return labels


def test_a_fresh_initiatives_architecture_is_ready_and_slice_plan_is_not(
    builder: TreeBuilder,
) -> None:
    builder.initiative(100)

    assert _ready(builder) == {"initiative 100: architecture"}


def test_marking_architecture_done_readies_slice_plan(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)

    builder.done(builder.step_node(initiative, ARCHITECTURE))

    assert _ready(builder) == {"initiative 100: slice_plan"}


def test_a_blocked_step_is_not_ready(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)

    builder.block(builder.step_node(initiative, ARCHITECTURE))

    assert _ready(builder) == set()


def test_a_step_with_a_blocked_parent_is_not_ready(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)

    builder.block(initiative)

    assert _ready(builder) == set()


def test_a_step_with_a_blocked_grandparent_is_not_ready(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    builder.done(builder.step_node(initiative, ARCHITECTURE))
    builder.done(builder.step_node(initiative, SLICE_PLAN))
    builder.slice(initiative, 101)
    builder.block(initiative)

    assert _ready(builder) == set()


def test_nothing_under_an_orphan_is_ready(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    builder.orphan(initiative)

    assert _ready(builder) == set()


def test_a_done_step_is_not_ready(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    architecture = builder.step_node(initiative, ARCHITECTURE)

    builder.done(architecture)

    assert "initiative 100: architecture" not in _ready(builder)


def test_implementation_is_sequential_across_slices_and_design_is_not(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    builder.done(builder.step_node(initiative, ARCHITECTURE))
    builder.done(builder.step_node(initiative, SLICE_PLAN))
    first = builder.slice(initiative, 101)
    second = builder.slice(initiative, 102)
    builder.done(builder.step_node(first, SLICE_DESIGN))
    builder.done(builder.step_node(first, TASKS))
    builder.done(builder.step_node(second, SLICE_DESIGN))
    builder.done(builder.step_node(second, TASKS))

    ready = _ready(builder)

    assert "slice 101: implementation" in ready
    assert "slice 102: implementation" not in ready
    assert "slice 102: tasks" not in ready  # already done

    builder.done(builder.step_node(first, IMPLEMENTATION))
    assert "slice 102: implementation" not in _ready(builder)
    builder.done(builder.step_node(first, MERGE))
    assert "slice 102: implementation" in _ready(builder)


def test_a_later_slices_design_is_ready_once_slice_plan_is_done(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    builder.done(builder.step_node(initiative, ARCHITECTURE))
    builder.done(builder.step_node(initiative, SLICE_PLAN))
    builder.slice(initiative, 101)
    builder.slice(initiative, 102)

    assert {"slice 101: slice_design", "slice 102: slice_design"} <= _ready(builder)


def test_the_result_is_deterministic_for_the_same_tree(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    builder.initiative(200)
    builder.done(builder.step_node(initiative, ARCHITECTURE))
    tree = builder.tree()

    first: list[Node] = list(tree.ready_steps())
    second: list[Node] = list(builder.tree().ready_steps())

    assert first == second == list(tree.ready_steps())
