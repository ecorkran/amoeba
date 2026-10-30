"""The unknown-status block: ``degraded`` or an out-of-vocabulary status."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from amoeba.runner.faults import TickFaults
from amoeba.runner.lifecycle.plan_read import PlanRead
from amoeba.runner.lifecycle.reconcile import reconcile
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import Store
from amoeba.store.inbox_models import Channel
from amoeba.store.models import Node, NodeKind, NodeStatus

from .reconcile_support import cf_initiative, cf_slice, plan, slice_list
from .tree_support import CF_PROJECT, PROJECT

ARCH = "120-arch.y.md"


@pytest.fixture
def store() -> Iterator[Store]:
    with Store.open_temporary() as opened:
        yield opened


def _read(*statuses: tuple[int, str]) -> PlanRead:
    return plan(
        cf_initiative(120, arch_file=ARCH),
        slices={120: slice_list(*(cf_slice(i, status=s) for i, s in statuses))},
    )


def _run(store: Store, read: PlanRead) -> tuple[bool, TickFaults]:
    faults = TickFaults()
    return reconcile(store, PROJECT, CF_PROJECT, read, faults), faults


def _slice(store: Store, index: int) -> Node:
    [node] = [
        n
        for n in store.nodes_for_project(PROJECT)
        if n.kind is NodeKind.SLICE and n.cf.index == index
    ]
    return node


def _block_count(store: Store, node: Node) -> int:
    return len(list(store.all_blocked_states(node.id)))


def _payloads(store: Store, node: Node) -> list[dict[str, object]]:
    return [
        dict(m.payload or {})
        for m in store.messages(PROJECT, channel=Channel.ESCALATION)
        if m.node_id == node.id
    ]


def test_a_new_degraded_slice_is_blocked_once(
    store: Store,
) -> None:
    wrote, faults = _run(store, _read((121, "degraded")))

    node = _slice(store, 121)
    assert wrote and len(faults) == 0, "no plan_read_failed"
    assert node.status is NodeStatus.BLOCKED_ON_HUMAN
    assert _block_count(store, node) == 1
    assert not [c for c in store.children_of(node.id) if c.cf.phase], "no steps"
    assert _payloads(store, node) == [
        {"fault_kind": "plan_status_unknown", "index": 121, "status": "degraded"}
    ]


def test_a_second_identical_read_writes_nothing(store: Store) -> None:
    _run(store, _read((121, "degraded")))

    wrote, _ = _run(store, _read((121, "degraded")))

    assert not wrote
    assert _block_count(store, _slice(store, 121)) == 1


def test_a_block_the_pm_resolved_is_restored_while_the_status_is_unknown(
    store: Store,
) -> None:
    _run(store, _read((121, "degraded")))
    store.resolve(_slice(store, 121).id, resolved_by="pm", detail="looked at it")
    assert _slice(store, 121).status is NodeStatus.RUNNABLE

    wrote, _ = _run(store, _read((121, "degraded")))

    assert wrote
    node = _slice(store, 121)
    assert node.status is NodeStatus.BLOCKED_ON_HUMAN
    assert _block_count(store, node) == 2


def test_once_cf_reports_a_known_status_the_node_is_not_blocked_again(
    store: Store,
) -> None:
    _run(store, _read((121, "degraded")))
    store.resolve(_slice(store, 121).id, resolved_by="pm", detail="fixed in CF")

    wrote, _ = _run(store, _read((121, "in_progress")))

    assert not wrote
    node = _slice(store, 121)
    assert node.status is NodeStatus.RUNNABLE and _block_count(store, node) == 1


def test_a_done_slice_is_not_blocked(store: Store) -> None:
    _run(store, _read((121, "in_progress")))
    store.update_node_status(_slice(store, 121).id, NodeStatus.DONE)

    _run(store, _read((121, "degraded")))

    node = _slice(store, 121)
    assert node.status is NodeStatus.DONE and _block_count(store, node) == 0


def test_an_out_of_vocabulary_status_blocks_with_its_raw_text(store: Store) -> None:
    _run(store, _read((121, "paused-by-pm")))

    node = _slice(store, 121)

    assert node.status is NodeStatus.BLOCKED_ON_HUMAN
    [payload] = _payloads(store, node)
    assert payload["status"] == "paused-by-pm"
    assert payload["fault_kind"] == "plan_status_unknown"


def test_the_next_slice_waits_for_the_unknown_slice_to_be_done(store: Store) -> None:
    _run(store, _read((121, "degraded"), (122, "not_started")))

    tree = LifecycleTree(store.nodes_for_project(PROJECT))
    ready = {n.cf.index for n in tree.ready_slices()}
    assert ready == set(), "121 is blocked and 122 waits for it"

    # Not vacuous: with the unknown slice resolved and done, 122 is ready.
    store.resolve(_slice(store, 121).id, resolved_by="pm", detail="skip it")
    store.update_node_status(_slice(store, 121).id, NodeStatus.DONE)
    after = LifecycleTree(store.nodes_for_project(PROJECT))
    assert {n.cf.index for n in after.ready_slices()} == {122}
