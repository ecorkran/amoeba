"""``LifecycleTree``: link lookup, children, is_linked."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from amoeba.store.models import NodeKind

from .tree_support import CF_PROJECT, TreeBuilder


@pytest.fixture
def builder() -> Iterator[TreeBuilder]:
    built = TreeBuilder()
    yield built
    built.close()


def test_lookup_distinguishes_initiative_120_from_slice_120(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(120)
    first_slice = builder.slice(initiative, 120)

    tree = builder.tree()

    assert tree.find_linked(NodeKind.INITIATIVE, CF_PROJECT, 120) == initiative
    assert tree.find_linked(NodeKind.SLICE, CF_PROJECT, 120) == first_slice
    assert tree.find_linked(NodeKind.SLICE, CF_PROJECT, 121) is None


def test_lookup_distinguishes_two_cf_projects(builder: TreeBuilder) -> None:
    left = builder.initiative(100, cf_project="cf-a")
    right = builder.initiative(100, cf_project="cf-b")

    tree = builder.tree()

    assert tree.find_linked(NodeKind.INITIATIVE, "cf-a", 100) == left
    assert tree.find_linked(NodeKind.INITIATIVE, "cf-b", 100) == right


def test_children_and_parent_follow_the_tree(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    child = builder.slice(initiative, 101)

    tree = builder.tree()

    assert child in tree.children(initiative)
    assert tree.parent(child) == initiative
    assert tree.parent(initiative) is None
    assert tree.children(child) == tuple(builder.store.children_of(child.id))
    assert child.id in {node.id for node in tree.nodes}


def test_a_slice_under_an_orphaned_initiative_is_not_linked(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    slice_node = builder.slice(initiative, 101)
    builder.orphan(initiative)

    tree = builder.tree()

    assert not tree.is_linked(builder.fresh(slice_node))
    assert not tree.is_linked(builder.fresh(initiative))


def test_an_unlinked_initiative_is_not_linked(builder: TreeBuilder) -> None:
    unlinked = builder.store.create_node(
        project_id=builder.project_id, kind=NodeKind.INITIATIVE, title="manual"
    )

    assert not builder.tree().is_linked(unlinked)
