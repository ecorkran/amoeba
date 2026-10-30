"""The create rule, through ``reconcile`` (orphan, then create)."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from amoeba.runner.faults import FaultKind, TickFaults
from amoeba.runner.lifecycle.plan_read import PlanRead, PlanReadFailed
from amoeba.runner.lifecycle.reconcile import reconcile
from amoeba.runner.lifecycle.tree import LifecycleTree
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


def test_linking_a_project_creates_initiative_and_slice_nodes_and_no_steps(
    store: Store,
) -> None:
    wrote, faults = _run(store, _fixture_plan())

    assert wrote and len(faults) == 0
    assert len(_nodes(store, NodeKind.INITIATIVE)) == 3
    assert len(_nodes(store, NodeKind.SLICE)) == 3, "123 is deferred: no node"
    assert _nodes(store, NodeKind.PHASE_OR_ARTIFACT) == []


def test_every_container_carries_its_project_and_index(
    store: Store,
) -> None:
    _run(store, _fixture_plan())

    for node in _nodes(store, NodeKind.INITIATIVE) + _nodes(store, NodeKind.SLICE):
        assert node.cf.project == CF_PROJECT and node.cf.index is not None
        assert node.status in {NodeStatus.RUNNABLE, NodeStatus.DONE}


def test_the_checked_initiatives_subtree_is_created_done(store: Store) -> None:
    _run(store, _fixture_plan())

    assert _linked(store, NodeKind.INITIATIVE, 100).status is NodeStatus.DONE
    assert _linked(store, NodeKind.SLICE, 101).status is NodeStatus.DONE


def test_an_incomplete_slice_is_runnable_and_so_is_its_initiative(
    store: Store,
) -> None:
    _run(store, _fixture_plan())

    assert _linked(store, NodeKind.SLICE, 121).status is NodeStatus.RUNNABLE
    assert _linked(store, NodeKind.INITIATIVE, 120).status is NodeStatus.RUNNABLE


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


def test_a_deferred_slice_has_no_node_and_gains_one_on_a_later_status(
    store: Store,
) -> None:
    _run(store, _fixture_plan())
    assert [n for n in _nodes(store, NodeKind.SLICE) if n.cf.index == 123] == []

    revived = _fixture_plan(
        slices_120=(
            cf_slice(121, status="in_progress", design_file=DESIGN_FILE),
            cf_slice(122, status="not_started"),
            cf_slice(123, status="in_progress"),
        )
    )
    wrote, _ = _run(store, revived)

    assert wrote
    assert _linked(store, NodeKind.SLICE, 123).status is NodeStatus.RUNNABLE


def test_a_slice_that_is_later_deferred_keeps_its_node_untouched(
    store: Store,
) -> None:
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
    assert _linked(store, NodeKind.SLICE, 122).status is NodeStatus.RUNNABLE


def test_rerunning_the_same_read_writes_nothing(store: Store) -> None:
    _run(store, _fixture_plan())
    before = store.nodes_for_project(PROJECT)

    wrote, faults = _run(store, _fixture_plan())

    assert not wrote and len(faults) == 0
    assert store.nodes_for_project(PROJECT) == before


def test_step_nodes_from_an_older_store_are_left_alone_and_never_ready(
    store: Store,
) -> None:
    initiative = store.create_node(
        project_id=PROJECT,
        kind=NodeKind.INITIATIVE,
        title="Initiative 140",
        cf=CFReference(project=CF_PROJECT, index=140),
    )
    old_step = store.create_node(
        project_id=PROJECT,
        kind=NodeKind.PHASE_OR_ARTIFACT,
        title="architecture",
        parent_id=initiative.id,
        cf=CFReference(project=CF_PROJECT, phase="architecture"),
    )

    _run(store, plan(cf_initiative(140)))

    assert len(_nodes(store, NodeKind.INITIATIVE)) == 1, "no second initiative"
    kept = store.get_node(old_step.id)
    assert kept is not None and kept.status is NodeStatus.RUNNABLE
    tree = LifecycleTree(store.nodes_for_project(PROJECT))
    assert all(node.kind is NodeKind.SLICE for node in tree.ready_slices())


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
