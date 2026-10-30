"""`ready_slices`: runnable, linked, unblocked, predecessor done (D1)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from amoeba.runner.lifecycle.predecessors import (
    slice_predecessor,
    slice_predecessor_done,
)

from .tree_support import TreeBuilder


@pytest.fixture
def builder() -> Iterator[TreeBuilder]:
    built = TreeBuilder()
    yield built
    built.close()


def _ready(builder: TreeBuilder) -> set[int]:
    """The CF indexes of the ready slices."""
    return {
        node.cf.index
        for node in builder.tree().ready_slices()
        if node.cf.index is not None
    }


def test_the_first_slice_of_an_initiative_is_ready_and_the_next_waits(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    builder.slice(initiative, 101, with_steps=False)
    builder.slice(initiative, 102, with_steps=False)

    assert _ready(builder) == {101}


def test_the_next_slice_is_ready_once_its_predecessor_is_done(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    first = builder.slice(initiative, 101, with_steps=False)
    builder.slice(initiative, 102, with_steps=False)

    builder.done(first)

    assert _ready(builder) == {102}


def test_the_predecessor_is_the_next_lower_index_not_the_next_created(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    high = builder.slice(initiative, 130, with_steps=False)
    low = builder.slice(initiative, 110, with_steps=False)
    mid = builder.slice(initiative, 120, with_steps=False)
    tree = builder.tree()

    assert slice_predecessor(tree, high) == mid
    assert slice_predecessor(tree, mid) == low
    assert slice_predecessor(tree, low) is None


def test_slices_of_another_initiative_are_not_predecessors(
    builder: TreeBuilder,
) -> None:
    first = builder.initiative(100)
    other = builder.initiative(200)
    builder.slice(first, 101, with_steps=False)
    only = builder.slice(other, 201, with_steps=False)

    assert slice_predecessor(builder.tree(), only) is None
    assert slice_predecessor_done(builder.tree(), only)
    assert _ready(builder) == {101, 201}


def test_an_orphaned_slice_is_neither_ready_nor_a_predecessor(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    gone = builder.slice(initiative, 101, with_steps=False)
    follower = builder.slice(initiative, 102, with_steps=False)
    builder.orphan(gone)

    assert slice_predecessor(builder.tree(), follower) is None
    assert _ready(builder) == {102}


def test_a_blocked_slice_is_not_ready(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    first = builder.slice(initiative, 101, with_steps=False)

    builder.block(first)

    assert _ready(builder) == set()


def test_a_slice_under_a_blocked_initiative_is_not_ready(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    builder.slice(initiative, 101, with_steps=False)

    builder.block(initiative)

    assert _ready(builder) == set()


def test_a_done_slice_is_not_ready(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    first = builder.slice(initiative, 101, with_steps=False)

    builder.done(first)

    assert _ready(builder) == set()
