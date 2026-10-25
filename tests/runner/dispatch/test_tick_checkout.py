"""D1 at tick level: a current step with no resolvable checkout blocks on a human."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.runner.dispatch.build_view import PAYLOAD_INDEX
from amoeba.runner.faults import PAYLOAD_FAULT_KIND, FaultKind
from amoeba.store import Channel, CommandKind, NodeStatus, Store
from runner.dispatch.tick_rig import DispatchRig

PROJECT = "demo"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    yield DispatchRig(tmp_path, store)


def _escalations(rig: DispatchRig) -> list[dict[str, object]]:
    messages = rig.store.messages(PROJECT, channel=Channel.ESCALATION)
    return [dict(message.payload or {}) for message in messages]


def _assert_blocked_unresolved(rig: DispatchRig, index: int, fragment: str) -> None:
    [payload] = _escalations(rig)
    assert payload[PAYLOAD_FAULT_KIND] == FaultKind.CHECKOUT_UNRESOLVED.value
    assert payload[PAYLOAD_INDEX] == index
    assert fragment in str(payload["reason"])


def test_an_index_no_range_holds_blocks_the_step(rig: DispatchRig) -> None:
    node = rig.step("orphan-range", 500)

    rig.tick()

    assert rig.status(node) is NodeStatus.BLOCKED_ON_HUMAN
    _assert_blocked_unresolved(rig, 500, "no worktree's range contains index 500")
    assert rig.entries(CommandKind.CF_WRITE, node) == []
    assert rig.popen.argvs == []


def test_an_index_two_ranges_hold_blocks_the_step(rig: DispatchRig) -> None:
    node = rig.step("overlap", 150)
    rig.snapshot(
        {
            "wt_a": rig.world.worktree_entry("wt_a", rig.world.root, 100, 199),
            "wt_b": rig.world.worktree_entry("wt_b", rig.world.second, 120, 299),
        }
    )

    rig.tick()

    assert rig.status(node) is NodeStatus.BLOCKED_ON_HUMAN
    _assert_blocked_unresolved(rig, 150, "all contain index 150")


def test_a_worktree_path_that_is_not_a_directory_blocks_the_step(
    rig: DispatchRig, tmp_path: Path
) -> None:
    node = rig.step("gone", 125)
    rig.snapshot(
        {"wt_a": rig.world.worktree_entry("wt_a", tmp_path / "nowhere", 100, 199)}
    )

    rig.tick()

    assert rig.status(node) is NodeStatus.BLOCKED_ON_HUMAN
    _assert_blocked_unresolved(rig, 125, "not an existing directory")


def test_no_observed_snapshot_blocks_the_step(tmp_path: Path, store: Store) -> None:
    rig = DispatchRig(tmp_path, store, with_snapshot=False)
    node = rig.step("unseen", 125)

    rig.tick()

    assert rig.status(node) is NodeStatus.BLOCKED_ON_HUMAN
    _assert_blocked_unresolved(rig, 125, "no observed snapshot")


def test_a_running_step_is_not_blocked_when_its_checkout_stops_resolving(
    rig: DispatchRig, tmp_path: Path
) -> None:
    node = rig.step("running", 125)
    rig.tick()
    rig.tick()
    assert rig.run_of(node)
    rig.snapshot(
        {"wt_a": rig.world.worktree_entry("wt_a", tmp_path / "nowhere", 100, 199)}
    )

    rig.tick()

    assert rig.status(node) is not NodeStatus.BLOCKED_ON_HUMAN
