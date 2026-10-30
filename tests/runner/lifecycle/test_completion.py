"""The complete rule: steps CF shows complete become done."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from amoeba.runner.faults import TickFaults
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.runner.lifecycle.plan_read import NoSlicePlan, PlanRead
from amoeba.runner.lifecycle.reconcile import reconcile
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import PARAM_RUN_ID, Store
from amoeba.store.journal_models import CommandKind
from amoeba.store.models import BlockedKind, Node, NodeKind, NodeStatus

from .reconcile_support import cf_initiative, cf_slice, plan, slice_list
from .tree_support import CF_PROJECT, PROJECT

ARCH = LifecycleStep.ARCHITECTURE
SLICE_PLAN = LifecycleStep.SLICE_PLAN
DESIGN = LifecycleStep.SLICE_DESIGN
IMPLEMENTATION = LifecycleStep.IMPLEMENTATION
MERGE = LifecycleStep.MERGE
INTEGRATION = LifecycleStep.INTEGRATION


@pytest.fixture
def store() -> Iterator[Store]:
    with Store.open_temporary() as opened:
        yield opened


def _run(store: Store, read: PlanRead) -> tuple[bool, TickFaults]:
    faults = TickFaults()
    return reconcile(store, PROJECT, CF_PROJECT, read, faults), faults


def _slice_read(status: str, *, checked: bool = False) -> PlanRead:
    return plan(
        cf_initiative(120, arch_file="120-arch.y.md"),
        slices={120: slice_list(cf_slice(121, status=status, is_checked=checked))},
    )


def _status(store: Store, node: Node) -> NodeStatus:
    current = store.get_node(node.id)
    assert current is not None
    return current.status


def test_a_done_step_is_untouched_and_a_rerun_writes_nothing(store: Store) -> None:
    _run(store, _slice_read("complete"))
    before = store.nodes_for_project(PROJECT)

    wrote, _ = _run(store, _slice_read("complete"))

    assert not wrote and store.nodes_for_project(PROJECT) == before


# -- the slice level (slice 132, D1) --------------------------------------------


def _slice_node(store: Store, index: int) -> Node:
    [found] = [
        n
        for n in store.nodes_for_project(PROJECT)
        if n.kind is NodeKind.SLICE and n.cf.index == index
    ]
    return found


def _initiative_node(store: Store, index: int) -> Node:
    [found] = [
        n
        for n in store.nodes_for_project(PROJECT)
        if n.kind is NodeKind.INITIATIVE and n.cf.index == index
    ]
    return found


def test_a_slice_cf_reports_complete_is_marked_done(store: Store) -> None:
    _run(store, _slice_read("in_progress"))
    assert _status(store, _slice_node(store, 121)) is NodeStatus.RUNNABLE

    _run(store, _slice_read("complete"))

    assert _status(store, _slice_node(store, 121)) is NodeStatus.DONE


def test_a_complete_slice_with_an_unresolved_entry_is_not_marked_done(
    store: Store,
) -> None:
    _run(store, _slice_read("in_progress"))
    node = _slice_node(store, 121)
    store.journal_issue(
        node.id,
        kind=CommandKind.SQ_RUN,
        parameters={PARAM_PIPELINE: "p", PARAM_PARAMS: {}, PARAM_RUN_ID: "run-1"},
    )

    _run(store, _slice_read("complete"))

    assert _status(store, node) is not NodeStatus.DONE


def test_a_blocked_complete_slice_is_left_alone(store: Store) -> None:
    _run(store, _slice_read("in_progress"))
    node = _slice_node(store, 121)
    store.block(node.id, kind=BlockedKind.HUMAN, context="stopped")

    _run(store, _slice_read("complete"))

    assert _status(store, node) is NodeStatus.BLOCKED_ON_HUMAN


def test_an_initiative_is_done_when_every_slice_under_it_is_done(
    store: Store,
) -> None:
    _run(store, _slice_read("in_progress"))
    assert _status(store, _initiative_node(store, 120)) is NodeStatus.RUNNABLE

    _run(store, _slice_read("complete"))

    assert _status(store, _initiative_node(store, 120)) is NodeStatus.DONE


def test_an_initiative_with_a_slice_still_to_do_is_not_done(store: Store) -> None:
    read = plan(
        cf_initiative(120, arch_file="120-arch.y.md"),
        slices={
            120: slice_list(
                cf_slice(121, status="complete"), cf_slice(122, status="in_progress")
            )
        },
    )

    _run(store, read)

    assert _status(store, _initiative_node(store, 120)) is NodeStatus.RUNNABLE


def test_an_initiative_with_no_slices_is_not_done(store: Store) -> None:
    _run(store, plan(cf_initiative(140), slices={140: NoSlicePlan()}))

    assert _status(store, _initiative_node(store, 140)) is NodeStatus.RUNNABLE
