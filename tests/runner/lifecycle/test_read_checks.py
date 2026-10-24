"""The read safety rules: what a read may be applied to, and the faults for the rest."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from amoeba.runner.faults import FaultKind
from amoeba.runner.lifecycle.plan_read import (
    NoSlicePlan,
    PlanRead,
    PlanReadFailed,
    SliceReadFailed,
)
from amoeba.runner.lifecycle.read_checks import ReadScope, checked_scope

from .reconcile_support import cf_initiative, cf_slice, plan, slice_list
from .tree_support import CF_PROJECT, TreeBuilder


@pytest.fixture
def builder() -> Iterator[TreeBuilder]:
    built = TreeBuilder()
    yield built
    built.close()


def _scope(builder: TreeBuilder, read: PlanRead | PlanReadFailed) -> ReadScope:
    return checked_scope(builder.tree(), CF_PROJECT, read)


def _details(scope: ReadScope) -> str:
    assert all(fault.kind is FaultKind.PLAN_READ_FAILED for fault in scope.faults)
    return " | ".join(fault.detail for fault in scope.faults)


def test_a_clean_read_is_fully_in_scope(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    builder.slice(initiative, 101)
    read = plan(
        cf_initiative(100), slices={100: slice_list(cf_slice(101), cf_slice(102))}
    )

    scope = _scope(builder, read)

    assert scope == ReadScope(True, frozenset({100}), ())


def test_a_duplicate_initiative_index_refuses_the_whole_read(
    builder: TreeBuilder,
) -> None:
    read = plan(cf_initiative(100), cf_initiative(100))

    scope = _scope(builder, read)

    assert not scope.initiatives and scope.slice_initiatives == frozenset()
    assert "100" in _details(scope)


def test_the_same_slice_index_under_two_initiatives_refuses_both(
    builder: TreeBuilder,
) -> None:
    read = plan(
        cf_initiative(100),
        cf_initiative(200),
        cf_initiative(300),
        slices={
            100: slice_list(cf_slice(150)),
            200: slice_list(cf_slice(150)),
            300: slice_list(cf_slice(301)),
        },
    )

    scope = _scope(builder, read)

    assert scope.initiatives
    assert scope.slice_initiatives == frozenset({300})
    assert "150" in _details(scope)


def test_a_repeated_index_inside_one_list_refuses_that_initiative(
    builder: TreeBuilder,
) -> None:
    read = plan(
        cf_initiative(100),
        cf_initiative(200),
        slices={
            100: slice_list(cf_slice(101), cf_slice(101)),
            200: slice_list(cf_slice(201)),
        },
    )

    scope = _scope(builder, read)

    assert scope.slice_initiatives == frozenset({200})
    assert "101" in _details(scope)


def test_empty_initiatives_with_linked_nodes_is_a_failed_read(
    builder: TreeBuilder,
) -> None:
    builder.initiative(100)
    builder.initiative(200)

    scope = _scope(builder, plan())

    assert not scope.initiatives and scope.slice_initiatives == frozenset()
    assert "2" in _details(scope)


def test_empty_initiatives_without_linked_nodes_is_valid(builder: TreeBuilder) -> None:
    scope = _scope(builder, plan())

    assert scope == ReadScope(True, frozenset(), ())


def test_an_unlinked_initiative_does_not_count_as_linked(builder: TreeBuilder) -> None:
    initiative = builder.initiative(100)
    builder.orphan(initiative)

    assert _scope(builder, plan()) == ReadScope(True, frozenset(), ())


def test_an_empty_slice_list_with_linked_slices_refuses_that_initiative(
    builder: TreeBuilder,
) -> None:
    initiative = builder.initiative(100)
    builder.slice(initiative, 101)
    builder.slice(initiative, 102)
    read = plan(cf_initiative(100), slices={100: slice_list()})

    scope = _scope(builder, read)

    assert scope.initiatives and scope.slice_initiatives == frozenset()
    assert "2" in _details(scope)


def test_an_empty_slice_list_without_linked_slices_is_valid(
    builder: TreeBuilder,
) -> None:
    builder.initiative(100)
    read = plan(cf_initiative(100), slices={100: slice_list()})

    assert _scope(builder, read) == ReadScope(True, frozenset({100}), ())


def test_a_failed_slice_read_narrows_only_its_initiative(builder: TreeBuilder) -> None:
    read = plan(
        cf_initiative(100),
        cf_initiative(200),
        slices={
            100: SliceReadFailed("`cf list slices 100` timed out"),
            200: slice_list(cf_slice(201)),
        },
    )

    scope = _scope(builder, read)

    assert scope.initiatives and scope.slice_initiatives == frozenset({200})
    assert len(scope.faults) == 1 and "slices 100" in _details(scope)


def test_a_no_plan_initiative_is_not_a_fault_and_has_no_slice_scope(
    builder: TreeBuilder,
) -> None:
    read = plan(cf_initiative(100), slices={100: NoSlicePlan()})

    assert _scope(builder, read) == ReadScope(True, frozenset(), ())


def test_a_failed_initiatives_read_removes_everything(builder: TreeBuilder) -> None:
    builder.initiative(100)

    scope = _scope(builder, PlanReadFailed("`cf list initiatives` exited 1"))

    assert not scope.initiatives and scope.slice_initiatives == frozenset()
    assert "exited 1" in _details(scope)
