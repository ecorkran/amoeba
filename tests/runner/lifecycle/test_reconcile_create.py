"""The create rule, through ``reconcile`` (orphan, then create)."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from amoeba.runner.faults import FaultKind, TickFaults
from amoeba.runner.lifecycle.plan_read import PlanRead, PlanReadFailed
from amoeba.runner.lifecycle.reconcile import reconcile
from amoeba.runner.lifecycle.steps import LifecycleStep, StepLevel, steps_at
from amoeba.store import Store
from amoeba.store.inbox_models import Channel
from amoeba.store.models import CFReference, Node, NodeKind, NodeStatus
from amoeba.upstream.context_forge import CFSliceEntry

from .reconcile_support import cf_initiative, cf_slice, plan, slice_list
from .tree_support import CF_PROJECT, PROJECT

DESIGN_FILE = "project-documents/user/slices/121-slice.the-design.md"


@pytest.fixture
def store() -> Iterator[Store]:
    with Store.open_temporary() as opened:
        yield opened


def _run(store: Store, read: PlanRead | PlanReadFailed) -> tuple[bool, TickFaults]:
    faults = TickFaults()
    return reconcile(store, PROJECT, CF_PROJECT, read, faults), faults


def _nodes(store: Store, kind: NodeKind) -> list[Node]:
    return [n for n in store.nodes_for_project(PROJECT) if n.kind is kind]


def _linked(store: Store, kind: NodeKind, index: int) -> Node:
    [node] = [n for n in _nodes(store, kind) if n.cf.index == index]
    return node


def _steps_of(store: Store, node: Node) -> dict[str, Node]:
    return {
        child.cf.phase or "": child
        for child in store.children_of(node.id)
        if child.kind is NodeKind.PHASE_OR_ARTIFACT
    }


def _fixture_plan(
    *,
    slices_100: tuple[CFSliceEntry, ...] | None = None,
    slices_120: tuple[CFSliceEntry, ...] | None = None,
) -> PlanRead:
    """Initiative 100 finished; 120 under way with three slices; 140 not started.

    The slice lists can be replaced to stage a later read of the same plan.
    """
    default_100 = (cf_slice(101, is_checked=True, status="complete"),)
    default_120 = (
        cf_slice(121, status="in_progress", design_file=DESIGN_FILE),
        cf_slice(122, status="not_started"),
        cf_slice(123, status="deferred"),
    )
    return plan(
        cf_initiative(
            100, arch_file="100-arch.x.md", is_checked=True, status="complete"
        ),
        cf_initiative(120, arch_file="120-arch.y.md"),
        cf_initiative(140, status="not_started"),
        slices={
            100: slice_list(*(slices_100 or default_100)),
            120: slice_list(*(slices_120 or default_120)),
        },
    )


def test_linking_a_project_creates_every_node_and_its_steps(store: Store) -> None:
    wrote, faults = _run(store, _fixture_plan())

    assert wrote and len(faults) == 0
    assert len(_nodes(store, NodeKind.INITIATIVE)) == 3
    assert len(_nodes(store, NodeKind.SLICE)) == 4
    initiative_steps = len(steps_at(StepLevel.INITIATIVE))
    slice_steps = len(steps_at(StepLevel.SLICE))
    expected_steps = 3 * initiative_steps + 3 * slice_steps  # 123 is deferred
    assert len(_nodes(store, NodeKind.PHASE_OR_ARTIFACT)) == expected_steps


def test_every_container_carries_its_index_and_every_step_a_phase(
    store: Store,
) -> None:
    _run(store, _fixture_plan())

    for node in _nodes(store, NodeKind.INITIATIVE) + _nodes(store, NodeKind.SLICE):
        assert node.cf.project == CF_PROJECT and node.cf.index is not None
        assert node.status in {NodeStatus.RUNNABLE, NodeStatus.DONE}
    for step in _nodes(store, NodeKind.PHASE_OR_ARTIFACT):
        assert step.cf.project == CF_PROJECT and step.cf.index is None
        assert step.cf.phase == step.title
        assert LifecycleStep(step.cf.phase)


def test_the_checked_initiatives_subtree_is_created_done(store: Store) -> None:
    _run(store, _fixture_plan())

    initiative = _linked(store, NodeKind.INITIATIVE, 100)
    slice_node = _linked(store, NodeKind.SLICE, 101)
    steps = [
        *_steps_of(store, initiative).values(),
        *_steps_of(store, slice_node).values(),
    ]
    assert len(steps) == 7
    assert all(step.status is NodeStatus.DONE for step in steps)


def test_an_initiative_without_an_arch_file_gets_a_runnable_architecture(
    store: Store,
) -> None:
    _run(store, _fixture_plan())

    steps = _steps_of(store, _linked(store, NodeKind.INITIATIVE, 140))

    assert steps[LifecycleStep.ARCHITECTURE].status is NodeStatus.RUNNABLE
    assert steps[LifecycleStep.SLICE_PLAN].status is NodeStatus.RUNNABLE


def test_an_in_progress_slice_gets_four_runnable_steps(store: Store) -> None:
    _run(store, _fixture_plan())

    steps = _steps_of(store, _linked(store, NodeKind.SLICE, 121))

    assert set(steps) == {step.value for step in steps_at(StepLevel.SLICE)}
    assert all(step.status is NodeStatus.RUNNABLE for step in steps.values())


def test_initiative_display_data_comes_from_cf(store: Store) -> None:
    _run(store, _fixture_plan())

    initiative = _linked(store, NodeKind.INITIATIVE, 120)

    assert initiative.title == "Initiative 120"
    assert initiative.cf.artifact_path == "120-arch.y.md"
    assert initiative.parent_id is None
    assert _linked(store, NodeKind.SLICE, 121).parent_id == initiative.id


def test_slice_name_comes_from_the_design_file_stem(store: Store) -> None:
    _run(store, _fixture_plan())

    node = _linked(store, NodeKind.SLICE, 121)

    assert node.cf.slice_name == "the-design"
    assert node.cf.artifact_path == DESIGN_FILE


def test_an_odd_design_file_leaves_slice_name_null_and_warns(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    read = plan(
        cf_initiative(120),
        slices={120: slice_list(cf_slice(121, design_file="notes/design.txt"))},
    )

    with caplog.at_level(logging.WARNING):
        _run(store, read)

    assert _linked(store, NodeKind.SLICE, 121).cf.slice_name is None
    assert any("notes/design.txt" in r.getMessage() for r in caplog.records)


def test_no_design_file_leaves_slice_name_null_without_a_warning(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        _run(store, _fixture_plan())

    assert _linked(store, NodeKind.SLICE, 122).cf.slice_name is None
    assert not [r for r in caplog.records if "design file" in r.getMessage()]


def test_a_deferred_slice_has_no_steps_and_gains_them_on_a_later_status(
    store: Store,
) -> None:
    _run(store, _fixture_plan())
    deferred = _linked(store, NodeKind.SLICE, 123)
    assert _steps_of(store, deferred) == {}

    revived = _fixture_plan(
        slices_120=(
            cf_slice(121, status="in_progress", design_file=DESIGN_FILE),
            cf_slice(122, status="not_started"),
            cf_slice(123, status="in_progress"),
        )
    )
    wrote, _ = _run(store, revived)

    assert wrote
    assert len(_steps_of(store, deferred)) == 4


def test_a_slice_with_steps_keeps_them_when_later_deferred(store: Store) -> None:
    _run(store, _fixture_plan())
    wrote, _ = _run(
        store,
        _fixture_plan(
            slices_120=(
                cf_slice(121, status="in_progress", design_file=DESIGN_FILE),
                cf_slice(122, status="deferred"),
                cf_slice(123, status="deferred"),
            )
        ),
    )

    assert not wrote
    assert len(_steps_of(store, _linked(store, NodeKind.SLICE, 122))) == 4


def test_rerunning_the_same_read_writes_nothing(store: Store) -> None:
    _run(store, _fixture_plan())
    before = store.nodes_for_project(PROJECT)

    wrote, faults = _run(store, _fixture_plan())

    assert not wrote and len(faults) == 0
    assert store.nodes_for_project(PROJECT) == before


def test_a_linked_node_missing_steps_gets_only_those_steps(store: Store) -> None:
    partial = store.create_node(
        project_id=PROJECT,
        kind=NodeKind.INITIATIVE,
        title="Initiative 140",
        cf=CFReference(project=CF_PROJECT, index=140),
    )
    store.create_node(
        project_id=PROJECT,
        kind=NodeKind.PHASE_OR_ARTIFACT,
        title="architecture",
        parent_id=partial.id,
        cf=CFReference(project=CF_PROJECT, phase=LifecycleStep.ARCHITECTURE.value),
    )

    wrote, _ = _run(store, plan(cf_initiative(140)))

    assert wrote
    assert len(_nodes(store, NodeKind.INITIATIVE)) == 1, "no second initiative"
    assert set(_steps_of(store, partial)) == {
        step.value for step in steps_at(StepLevel.INITIATIVE)
    }
    architecture = _steps_of(store, partial)[LifecycleStep.ARCHITECTURE]
    assert architecture.status is NodeStatus.RUNNABLE, "the existing step is untouched"


def test_renumber_yields_one_orphan_and_one_new_node(store: Store) -> None:
    _run(store, _fixture_plan())
    old = _linked(store, NodeKind.SLICE, 121)
    renumbered = _fixture_plan(
        slices_120=(
            cf_slice(124, status="in_progress", design_file=DESIGN_FILE),
            cf_slice(122, status="not_started"),
            cf_slice(123, status="deferred"),
        )
    )

    wrote, faults = _run(store, renumbered)

    assert wrote and len(faults) == 0
    orphan = store.get_node(old.id)
    assert orphan is not None
    assert orphan.cf.index is None and orphan.cf.slice_name is None
    assert orphan.status is NodeStatus.BLOCKED_ON_HUMAN
    assert len(store.open_project_escalations(PROJECT)) == 0
    assert len(store.messages(PROJECT, channel=Channel.ESCALATION)) == 1
    created = _linked(store, NodeKind.SLICE, 124)
    assert created.id != old.id and created.cf.slice_name == "the-design"
    assert len(_steps_of(store, created)) == 4


def test_a_slice_listed_under_another_initiative_is_orphaned_and_recreated(
    store: Store,
) -> None:
    _run(store, _fixture_plan())
    old = _linked(store, NodeKind.SLICE, 101)
    moved = _fixture_plan(
        slices_100=(cf_slice(102, is_checked=True, status="complete"),),
        slices_120=(
            cf_slice(101, status="in_progress"),
            cf_slice(121, status="in_progress", design_file=DESIGN_FILE),
            cf_slice(122, status="not_started"),
            cf_slice(123, status="deferred"),
        ),
    )

    _run(store, moved)

    assert store.get_node(old.id) is not None
    assert (store.get_node(old.id) or old).cf.index is None
    recreated = _linked(store, NodeKind.SLICE, 101)
    assert recreated.id != old.id
    assert recreated.parent_id == _linked(store, NodeKind.INITIATIVE, 120).id


def test_a_failed_read_creates_nothing_and_raises_a_fault(store: Store) -> None:
    wrote, faults = _run(store, PlanReadFailed("`cf list initiatives` exited 1"))

    assert not wrote
    assert store.nodes_for_project(PROJECT) == []
    assert [fault.kind for fault in faults] == [FaultKind.PLAN_READ_FAILED]
