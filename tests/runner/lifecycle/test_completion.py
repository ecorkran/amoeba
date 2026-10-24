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


def _step(store: Store, kind: NodeKind, index: int, step: LifecycleStep) -> Node:
    [owner] = [
        n
        for n in store.nodes_for_project(PROJECT)
        if n.kind is kind and n.cf.index == index
    ]
    [found] = [c for c in store.children_of(owner.id) if c.cf.phase == step.value]
    return found


def _status(store: Store, node: Node) -> NodeStatus:
    current = store.get_node(node.id)
    assert current is not None
    return current.status


def test_no_slice_plan_keeps_slice_plan_runnable_and_raises_no_fault(
    store: Store,
) -> None:
    read = plan(cf_initiative(140), slices={140: NoSlicePlan()})

    _, faults = _run(store, read)

    step = _step(store, NodeKind.INITIATIVE, 140, SLICE_PLAN)
    assert _status(store, step) is NodeStatus.RUNNABLE and len(faults) == 0


def test_a_later_slice_list_completes_slice_plan(store: Store) -> None:
    _run(store, plan(cf_initiative(140), slices={140: NoSlicePlan()}))

    wrote, _ = _run(
        store, plan(cf_initiative(140), slices={140: slice_list(cf_slice(141))})
    )

    step = _step(store, NodeKind.INITIATIVE, 140, SLICE_PLAN)
    assert wrote and _status(store, step) is NodeStatus.DONE


def test_architecture_completes_when_an_arch_file_appears(store: Store) -> None:
    _run(store, plan(cf_initiative(140)))
    step = _step(store, NodeKind.INITIATIVE, 140, ARCH)
    assert _status(store, step) is NodeStatus.RUNNABLE

    _run(store, plan(cf_initiative(140, arch_file="140-arch.z.md")))

    assert _status(store, step) is NodeStatus.DONE


def test_slice_steps_complete_when_cf_reports_the_slice_complete(
    store: Store,
) -> None:
    _run(store, _slice_read("in_progress"))
    steps = [
        _step(store, NodeKind.SLICE, 121, s) for s in (DESIGN, IMPLEMENTATION, MERGE)
    ]
    assert all(_status(store, s) is NodeStatus.RUNNABLE for s in steps)

    _run(store, _slice_read("complete"))

    assert all(_status(store, s) is NodeStatus.DONE for s in steps)


def test_integration_completes_from_is_checked_and_not_from_status(
    store: Store,
) -> None:
    complete_unchecked = plan(
        cf_initiative(120, arch_file="a.md", status="complete", is_checked=False)
    )
    _run(store, complete_unchecked)
    step = _step(store, NodeKind.INITIATIVE, 120, INTEGRATION)
    assert _status(store, step) is NodeStatus.RUNNABLE

    _run(store, plan(cf_initiative(120, arch_file="a.md", is_checked=True)))

    assert _status(store, step) is NodeStatus.DONE


def test_a_step_with_an_unresolved_journal_entry_is_not_marked_done(
    store: Store,
) -> None:
    _run(store, _slice_read("in_progress"))
    step = _step(store, NodeKind.SLICE, 121, IMPLEMENTATION)
    store.journal_issue(
        step.id,
        kind=CommandKind.SQ_RUN,
        parameters={PARAM_PIPELINE: "p", PARAM_PARAMS: {}, PARAM_RUN_ID: "run-1"},
    )

    _run(store, _slice_read("complete"))

    assert _status(store, step) is not NodeStatus.DONE
    assert _status(store, _step(store, NodeKind.SLICE, 121, DESIGN)) is NodeStatus.DONE


def test_a_blocked_human_step_is_resolved_by_the_runner_then_done(
    store: Store,
) -> None:
    _run(store, plan(cf_initiative(140)))
    step = _step(store, NodeKind.INITIATIVE, 140, ARCH)
    store.block(step.id, kind=BlockedKind.HUMAN, context="architecture is a human step")

    _run(store, plan(cf_initiative(140, arch_file="140-arch.z.md")))

    assert _status(store, step) is NodeStatus.DONE
    [state] = list(store.all_blocked_states(step.id))
    assert state.resolution is not None and state.resolution.resolved_by == "runner"


def test_a_blocked_pipeline_step_is_left_alone(store: Store) -> None:
    _run(store, _slice_read("in_progress"))
    step = _step(store, NodeKind.SLICE, 121, DESIGN)
    store.block(step.id, kind=BlockedKind.HUMAN, context="reviewing")

    _run(store, _slice_read("complete"))

    assert _status(store, step) is NodeStatus.BLOCKED_ON_HUMAN


def test_a_crash_between_the_resolve_and_the_status_write_is_repaired(
    store: Store,
) -> None:
    _run(store, plan(cf_initiative(140)))
    step = _step(store, NodeKind.INITIATIVE, 140, ARCH)
    store.block(step.id, kind=BlockedKind.HUMAN, context="human step")
    store.resolve(step.id, resolved_by="runner", detail="observed: crashed here")
    assert _status(store, step) is NodeStatus.RUNNABLE

    _run(store, plan(cf_initiative(140, arch_file="140-arch.z.md")))

    assert _status(store, step) is NodeStatus.DONE
    assert len(list(store.all_blocked_states(step.id))) == 1


def test_a_done_step_is_untouched_and_a_rerun_writes_nothing(store: Store) -> None:
    _run(store, _slice_read("complete"))
    before = store.nodes_for_project(PROJECT)

    wrote, _ = _run(store, _slice_read("complete"))

    assert not wrote and store.nodes_for_project(PROJECT) == before
