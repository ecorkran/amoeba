"""The plan stage in the project tick: cadence, trigger, cut-off, probes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from amoeba.process import RunOutcome
from amoeba.runner.budget import TickResult
from amoeba.store import (
    CFSnapshotInput,
    CFSnapshotOutcome,
    NodeKind,
    NodeStatus,
    Store,
)
from runner.observe_support import CfReply, document
from runner.plan_tick_support import (
    INITIATIVES_KEY,
    initiatives_json,
    serve_plan,
    slices_json,
    slices_key,
)
from runner.tick_support import PLAN_READ_INTERVAL, PROJECT, Rig, link

LINK = "cf-1"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Rig:
    built = Rig(tmp_path, store)
    built.planners = ()  # the production tuple is empty
    link(store, "s-1", LINK, PROJECT)
    serve_plan(built.cf, (100,), {100: (101,)})
    return built


def _plan_calls(rig: Rig) -> list[str]:
    return [
        " ".join(call[1:4])
        for call in rig.cf.calls
        if call[1] == "list" and call[2] == "slices"
    ]


def _kinds(store: Store, kind: NodeKind) -> list[int]:
    return sorted(
        n.cf.index
        for n in store.nodes_for_project(PROJECT)
        if n.kind is kind and n.cf.index is not None
    )


def test_the_first_tick_reads_and_reconciles_the_plan(rig: Rig, store: Store) -> None:
    result, tick = rig.tick()

    assert result is TickResult.COMPLETE and tick.wrote
    assert _kinds(store, NodeKind.INITIATIVE) == [100]
    assert _kinds(store, NodeKind.SLICE) == [101]


def test_the_view_tree_shows_the_nodes_the_tick_just_created(
    rig: Rig, store: Store
) -> None:
    rig.planners = (rig.planner,)
    rig.tick()

    [view] = rig.planner.views
    assert {n.cf.index for n in view.tree.nodes if n.kind is NodeKind.SLICE} == {101}


def test_a_tick_before_the_interval_reads_nothing(rig: Rig) -> None:
    rig.tick()
    calls = len(rig.cf.calls)

    rig.clock.seconds = PLAN_READ_INTERVAL - 1.0
    rig.tick()

    assert len(rig.cf.calls) == calls


def test_after_the_interval_a_new_slice_gets_a_node_without_a_pointer_change(
    rig: Rig, store: Store
) -> None:
    rig.tick()
    serve_plan(rig.cf, (100,), {100: (101, 102)})

    rig.clock.seconds = PLAN_READ_INTERVAL
    rig.tick()

    assert _kinds(store, NodeKind.SLICE) == [101, 102]


def _changed_snapshot(snapshot_id_hint: int) -> CFSnapshotInput:
    return CFSnapshotInput(
        project_id=PROJECT,
        cf_project_id=LINK,
        outcome=CFSnapshotOutcome.OBSERVED,
        state={"activeSlice": str(snapshot_id_hint)},
        changed=[{"field": "activeSlice"}],
        detail=None,
        cf_updated_at=None,
        cf_version_label="test",
        observed_at=datetime(2026, 10, 23, tzinfo=UTC),
    )


def test_a_changed_snapshot_triggers_an_early_read(rig: Rig, store: Store) -> None:
    rig.tick()
    serve_plan(rig.cf, (100,), {100: (101, 102)})
    rig.clock.seconds = 1.0
    rig.tick()
    assert _kinds(store, NodeKind.SLICE) == [101], "no read before the interval"

    store.record_cf_snapshot(_changed_snapshot(1))
    rig.clock.seconds = 2.0
    rig.tick()

    assert _kinds(store, NodeKind.SLICE) == [101, 102]


def test_a_cut_off_read_applies_nothing_raises_no_fault_and_is_read_again(
    rig: Rig, store: Store
) -> None:
    rig.deadline = 5.0
    # status, probe initiatives, plan initiatives; then the budget is spent.
    rig.cf.on_call = lambda: (
        setattr(rig.clock, "seconds", 99.0) if len(rig.cf.calls) == 3 else None
    )

    result, _ = rig.tick()

    assert result is TickResult.CUT_OFF
    assert store.nodes_for_project(PROJECT) == []
    assert store.open_project_escalations(PROJECT) == []

    rig.deadline = 1_000_000.0
    rig.cf.on_call = None
    result, _ = rig.tick()

    assert result is TickResult.COMPLETE
    assert _kinds(store, NodeKind.SLICE) == [101]


def test_a_cut_off_poll_leaves_no_plan_read(tmp_path: Path, store: Store) -> None:
    rig = Rig(tmp_path, store, document("x", RunOutcome.TIMED_OUT))
    rig.planners = ()
    link(store, "s-1", LINK, PROJECT)
    serve_plan(rig.cf, (100,), {100: (101,)})
    rig.deadline = 0.0

    result, _ = rig.tick()

    assert result is TickResult.CUT_OFF
    assert rig.cf.calls == []
    assert store.nodes_for_project(PROJECT) == []


def test_a_probe_failed_link_is_not_read(rig: Rig, store: Store) -> None:
    rig.cf.replies["status"] = CfReply("", 1, "boom")

    rig.tick()

    assert _plan_calls(rig) == []
    assert INITIATIVES_KEY not in [" ".join(c[1:3]) for c in rig.cf.calls[1:]]
    assert store.nodes_for_project(PROJECT) == []


def test_two_links_in_one_project_keep_independent_state(
    rig: Rig, store: Store
) -> None:
    link(store, "s-2", "cf-2", PROJECT)
    rig.cf.replies[f"{INITIATIVES_KEY}@cf-2"] = CfReply(initiatives_json(200))
    rig.cf.replies[f"{slices_key(200)}@cf-2"] = CfReply(slices_json(201))
    rig.tick()
    assert _kinds(store, NodeKind.INITIATIVE) == [100, 200]

    rig.cf.replies[f"{slices_key(200)}@cf-2"] = CfReply(slices_json(201, 202))
    rig.clock.seconds = PLAN_READ_INTERVAL
    rig.tick()

    assert _kinds(store, NodeKind.SLICE) == [101, 201, 202]


def test_the_empty_production_planners_create_nodes_launch_nothing_and_raise_nothing(
    rig: Rig, store: Store
) -> None:
    rig.tick()
    rig.clock.seconds = PLAN_READ_INTERVAL
    rig.tick()

    assert rig.popen.calls == 0
    assert store.unresolved_journal_entries(PROJECT) == []
    assert store.open_project_escalations(PROJECT) == []
    assert not [
        n
        for n in store.nodes_for_project(PROJECT)
        if n.status is NodeStatus.BLOCKED_ON_HUMAN
    ]
