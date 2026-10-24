"""Crash repair: a write failing at any point is repaired by the next reconcile."""

from __future__ import annotations

from typing import Any

import pytest

from amoeba.runner.faults import TickFaults
from amoeba.runner.lifecycle.plan_read import PlanRead
from amoeba.runner.lifecycle.reconcile import reconcile
from amoeba.store import Store

from .reconcile_support import cf_initiative, cf_slice, plan, slice_list
from .tree_support import CF_PROJECT, PROJECT

#: The store methods that write nodes; the proxy counts and can fail each call.
WRITES = frozenset(
    {"create_node", "block", "resolve", "update_node_status", "update_cf_reference"}
)


class CrashingStore:
    """Delegates to a real store; the ``fail_at``-th write raises instead."""

    def __init__(self, store: Store, fail_at: int | None) -> None:
        self._store = store
        self._fail_at = fail_at
        self.writes = 0

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._store, name)
        if name not in WRITES:
            return attribute

        def counted(*args: Any, **kwargs: Any) -> Any:
            self.writes += 1
            if self.writes == self._fail_at:
                raise RuntimeError(f"simulated crash at write {self.writes}")
            return attribute(*args, **kwargs)

        return counted


def _read() -> PlanRead:
    """Every rule has work: creates, a done subtree, and an unknown-status block."""
    return plan(
        cf_initiative(100, arch_file="100-arch.x.md", is_checked=True),
        cf_initiative(120, arch_file="120-arch.y.md"),
        cf_initiative(140),
        slices={
            100: slice_list(cf_slice(101, is_checked=True, status="complete")),
            120: slice_list(
                cf_slice(121, status="in_progress", design_file="1-slice.a.md"),
                cf_slice(122, status="degraded"),
            ),
        },
    )


def _canonical(store: Store) -> list[tuple[object, ...]]:
    nodes = store.nodes_for_project(PROJECT)
    by_id = {node.id: node for node in nodes}

    def label(node_id: str | None) -> tuple[object, ...]:
        if node_id is None:
            return ()
        parent = by_id[node_id]
        return (parent.kind.value, parent.cf.index, parent.title)

    return sorted(
        (
            node.kind.value,
            node.cf.index,
            node.cf.phase,
            node.status.value,
            node.title,
            label(node.parent_id),
            node.cf.slice_name,
        )
        for node in nodes
    )


def _reconcile(store: Any) -> None:
    reconcile(store, PROJECT, CF_PROJECT, _read(), TickFaults())


def _uninterrupted() -> tuple[list[tuple[object, ...]], int]:
    with Store.open_temporary() as store:
        counting = CrashingStore(store, None)
        _reconcile(counting)
        return _canonical(store), counting.writes


EXPECTED, TOTAL_WRITES = _uninterrupted()


def test_the_uninterrupted_run_has_work_for_every_kind_of_write() -> None:
    assert TOTAL_WRITES > 20
    statuses = {row[3] for row in EXPECTED}
    assert {"done", "runnable", "blocked_on_human"} <= statuses


@pytest.mark.parametrize("fail_at", range(1, TOTAL_WRITES + 1))
def test_a_fresh_reconcile_after_a_crash_reaches_the_uninterrupted_tree(
    fail_at: int,
) -> None:
    with Store.open_temporary() as store:
        with pytest.raises(RuntimeError, match="simulated crash"):
            _reconcile(CrashingStore(store, fail_at))

        _reconcile(store)

        assert _canonical(store) == EXPECTED
        linked = [(row[0], row[1]) for row in _canonical(store) if row[1] is not None]
        assert len(linked) == len(set(linked)), "no duplicate linked nodes"
