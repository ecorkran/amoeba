"""The orphan rule, on nodes staged in a real store."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from amoeba.runner.faults import FaultKind
from amoeba.runner.lifecycle.orphaning import orphan_unlisted
from amoeba.runner.lifecycle.plan_read import (
    PlanRead,
    PlanReadFailed,
    SliceReadFailed,
)
from amoeba.runner.lifecycle.read_checks import checked_scope
from amoeba.store.models import BlockedKind, CFReference, Node, NodeStatus

from .reconcile_support import cf_initiative, cf_slice, plan, slice_list
from .tree_support import CF_PROJECT, TreeBuilder


@pytest.fixture
def builder() -> Iterator[TreeBuilder]:
    built = TreeBuilder()
    yield built
    built.close()


def _orphan(builder: TreeBuilder, read: PlanRead | PlanReadFailed) -> bool:
    tree = builder.tree()
    scope = checked_scope(tree, CF_PROJECT, read)
    return orphan_unlisted(builder.store, tree, CF_PROJECT, read, scope)


def _open_block_count(builder: TreeBuilder, node: Node) -> int:
    return sum(
        1
        for state in builder.store.all_blocked_states(node.id)
        if state.resolution is None
    )


def _named(builder: TreeBuilder, node: Node, slice_name: str) -> Node:
    return builder.store.update_cf_reference(
        node.id,
        CFReference(
            project=node.cf.project, index=node.cf.index, slice_name=slice_name
        ),
    )


def test_a_renumbered_slice_is_orphaned_once(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    old = builder.slice(initiative, 101)
    read = plan(cf_initiative(100), slices={100: slice_list(cf_slice(102))})

    assert _orphan(builder, read)

    node = builder.fresh(old)
    assert node.cf.index is None and node.cf.slice_name is None
    assert node.status is NodeStatus.BLOCKED_ON_HUMAN
    assert _open_block_count(builder, node) == 1


def test_the_orphan_block_names_the_former_values(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    old = _named(builder, builder.slice(initiative, 101), "101-slice.old-name")
    read = plan(cf_initiative(100), slices={100: slice_list(cf_slice(102))})

    _orphan(builder, read)

    state = builder.store.blocked_state_for(old.id)
    assert state is not None and state.kind is BlockedKind.HUMAN
    assert state.context == "orphaned: CF no longer reports index 101"
    assert builder.escalation_payloads(old) == [
        {
            "fault_kind": FaultKind.LIFECYCLE_ORPHAN.value,
            "cf_project_id": CF_PROJECT,
            "former_index": 101,
            "former_slice_name": "101-slice.old-name",
        }
    ]


def test_an_initiative_missing_from_the_read_is_orphaned(builder: TreeBuilder) -> None:
    builder.initiative(100)
    gone = builder.initiative(200)

    assert _orphan(builder, plan(cf_initiative(100)))

    assert builder.fresh(gone).cf.index is None
    assert builder.fresh(gone).status is NodeStatus.BLOCKED_ON_HUMAN


def test_a_moved_slice_is_orphaned(builder: TreeBuilder) -> None:
    first = builder.initiative(100)
    second = builder.initiative(200)
    moved = builder.slice(first, 101)
    builder.slice(first, 102)
    builder.slice(second, 201)
    read = plan(
        cf_initiative(100),
        cf_initiative(200),
        slices={
            100: slice_list(cf_slice(102)),
            200: slice_list(cf_slice(101), cf_slice(201)),
        },
    )

    assert _orphan(builder, read)

    assert builder.fresh(moved).cf.index is None
    assert builder.fresh(first).cf.index == 100, "the other slices' parent is untouched"


def test_a_completed_slice_leaving_the_plan_is_unlinked_and_not_blocked(
    builder: TreeBuilder, caplog: pytest.LogCaptureFixture
) -> None:
    initiative = builder.initiative(100)
    finished = builder.slice(initiative, 101)
    builder.slice(initiative, 102)
    builder.done(finished)
    read = plan(cf_initiative(100), slices={100: slice_list(cf_slice(102))})

    with caplog.at_level(logging.INFO):
        assert _orphan(builder, read)

    node = builder.fresh(finished)
    assert node.cf.index is None and node.status is NodeStatus.DONE
    assert builder.store.blocked_state_for(node.id, include_resolved=True) is None
    assert any(r.levelno == logging.INFO for r in caplog.records)


def test_an_already_blocked_orphan_keeps_its_one_escalation(
    builder: TreeBuilder, caplog: pytest.LogCaptureFixture
) -> None:
    initiative = builder.initiative(100)
    blocked = builder.slice(initiative, 101)
    builder.slice(initiative, 102)
    builder.block(blocked)
    read = plan(cf_initiative(100), slices={100: slice_list(cf_slice(102))})

    with caplog.at_level(logging.WARNING):
        assert _orphan(builder, read)

    node = builder.fresh(blocked)
    assert node.cf.index is None
    assert _open_block_count(builder, node) == 1
    warning = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warning and "101" in warning[0].getMessage()


def test_empty_list_with_linked_nodes_orphans_nothing(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    child = builder.slice(initiative, 101)

    assert not _orphan(builder, plan())
    assert not _orphan(builder, plan(cf_initiative(100), slices={100: slice_list()}))

    assert builder.fresh(initiative).cf.index == 100
    assert builder.fresh(child).cf.index == 101
    assert builder.fresh(child).status is NodeStatus.RUNNABLE


def test_a_failed_slice_read_orphans_none_of_that_initiatives_slices(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    child = builder.slice(initiative, 101)
    read = plan(cf_initiative(100), slices={100: SliceReadFailed("timed out")})

    assert not _orphan(builder, read)

    assert builder.fresh(child).cf.index == 101


def test_a_failed_initiatives_read_orphans_nothing(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)

    assert not _orphan(builder, PlanReadFailed("exited 1"))

    assert builder.fresh(initiative).cf.index == 100


def test_an_unlinked_node_is_never_orphaned_again(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    old = builder.slice(initiative, 101)
    builder.slice(initiative, 102)
    read = plan(cf_initiative(100), slices={100: slice_list(cf_slice(102))})
    assert _orphan(builder, read)
    before = list(builder.store.all_blocked_states(old.id))

    assert not _orphan(builder, read)

    assert list(builder.store.all_blocked_states(old.id)) == before


def test_descendants_are_untouched_and_nothing_is_deleted(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    old = builder.slice(initiative, 101)
    builder.slice(initiative, 102)
    count = len(builder.store.nodes_for_project(builder.project_id))
    steps_before = [builder.fresh(c) for c in builder.store.children_of(old.id)]
    read = plan(cf_initiative(100), slices={100: slice_list(cf_slice(102))})

    _orphan(builder, read)

    assert len(builder.store.nodes_for_project(builder.project_id)) == count
    assert [builder.fresh(c) for c in builder.store.children_of(old.id)] == steps_before
    tree = builder.tree()
    assert all(not tree.is_linked(step) for step in tree.children(builder.fresh(old)))
