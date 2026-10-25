"""D11 at tick level: a pointer moved from under a running step escalates."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from amoeba.process import RunOutcome
from amoeba.runner.dispatch.pointer_watch import PAYLOAD_RUNS
from amoeba.store import CommandKind, Message, Node, Store
from runner.dispatch.tick_rig import DispatchRig

PROJECT = "demo"
MOVED = "130-slice.someone-else"
HOME = "125-slice.mine"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    yield DispatchRig(tmp_path, store)


def _worktrees(rig: DispatchRig, active: str) -> dict[str, dict[str, object]]:
    world = rig.world
    return {
        "wt_a": {
            **world.worktree_entry("wt_a", world.root, 100, 199),
            "activeSlice": active,
        },
        "wt_b": world.worktree_entry("wt_b", world.second, 200, 299),
    }


def _point_cf_at(rig: DispatchRig, active: str) -> None:
    """Record a snapshot, taken now, in which the first worktree reads ``active``."""
    rig.snapshot(_worktrees(rig, active), observed_at=datetime.now(UTC))


def _running(rig: DispatchRig) -> Node:
    node = rig.step("running", 125)
    rig.tick()
    rig.tick()
    assert rig.run_of(node)
    return node


def _open(rig: DispatchRig) -> list[Message]:
    return [
        m
        for m in rig.store.open_project_escalations(PROJECT)
        if m.fault_kind == "pointer_moved"
    ]


def test_a_snapshot_moving_the_runs_worktree_raises_one_escalation(
    rig: DispatchRig,
) -> None:
    node = _running(rig)
    assert _open(rig) == []

    _point_cf_at(rig, MOVED)
    rig.tick()

    [escalation] = _open(rig)
    payload = dict(escalation.payload or {})
    [listed] = payload[PAYLOAD_RUNS]  # type: ignore[misc]
    assert listed["node_id"] == node.id  # pyright: ignore[reportUnknownMemberType]
    assert listed["worktree_id"] == "wt_a"  # pyright: ignore[reportUnknownMemberType]
    assert listed["observed"] == MOVED  # pyright: ignore[reportUnknownMemberType]


def test_it_stays_open_while_the_snapshot_holds_and_adds_no_second(
    rig: DispatchRig,
) -> None:
    _running(rig)
    _point_cf_at(rig, MOVED)
    rig.tick()
    [first] = _open(rig)

    rig.tick()
    rig.tick()

    [still] = _open(rig)
    assert still.id == first.id


def test_it_closes_when_the_pointer_returns(rig: DispatchRig) -> None:
    _running(rig)
    _point_cf_at(rig, MOVED)
    rig.tick()
    assert len(_open(rig)) == 1

    _point_cf_at(rig, HOME)
    rig.tick()

    assert _open(rig) == []


def test_it_closes_when_the_run_ends_and_the_run_is_ingested(
    rig: DispatchRig,
) -> None:
    node = _running(rig)
    entry = rig.run_of(node)
    _point_cf_at(rig, MOVED)
    rig.tick()
    assert len(_open(rig)) == 1

    rig.end_run(node, RunOutcome.COMPLETED)

    done = rig.store.journal_entry(entry.id)
    assert done is not None and done.is_resolved
    assert rig.store.routing_decision_for_entry(entry.id) is not None, "routed"
    assert _open(rig) == []
    assert len(rig.entries(CommandKind.SQ_RUN, node)) == 1


def test_a_snapshot_that_still_reads_the_runs_slice_raises_nothing(
    rig: DispatchRig,
) -> None:
    _running(rig)
    _point_cf_at(rig, HOME)

    rig.tick()

    assert _open(rig) == []
