"""D4 at tick level: one pipeline per checkout, held from its launch."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sq_stub_scripts import missing_file_review

from amoeba.process import RunOutcome
from amoeba.store import CommandKind, Node, NodeStatus, Store
from runner.dispatch.tick_rig import DispatchRig

FIRST_INDEX = 125
SECOND_INDEX = 126
OTHER_WORKTREE_INDEX = 225


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    yield DispatchRig(tmp_path, store)


def _launches(rig: DispatchRig, node: Node) -> int:
    return len(rig.entries(CommandKind.SQ_RUN, node))


def _two_in_one_checkout(rig: DispatchRig) -> tuple[Node, Node]:
    first = rig.step("first", FIRST_INDEX)
    second = rig.step("second", SECOND_INDEX)
    return first, second


def test_second_slice_waits_for_checkout(rig: DispatchRig) -> None:
    first, second = _two_in_one_checkout(rig)

    rig.tick()
    assert _launches(rig, first) == 1, "the first launches at once"
    assert _launches(rig, second) == 0, "in flight"

    assert len(rig.popen.argvs) == 1


def test_the_second_slice_is_dispatched_the_tick_the_first_run_completes(
    rig: DispatchRig,
) -> None:
    first, second = _two_in_one_checkout(rig)
    rig.tick()
    assert _launches(rig, second) == 0

    rig.end_run(first, RunOutcome.COMPLETED)

    assert _launches(rig, second) == 1
    assert rig.entries(CommandKind.CF_WRITE, first) == []


def test_a_failed_run_keeps_its_checkout_until_released(
    rig: DispatchRig,
) -> None:
    first, second = _two_in_one_checkout(rig)
    rig.tick()

    rig.end_run(
        first,
        RunOutcome.FAILED,
        failure={"kind": "cost_cap", "step": "s", "message": "m"},
    )

    assert rig.status(first) is NodeStatus.BLOCKED_ON_HUMAN
    assert _launches(rig, second) == 0, "the failed run may be resumed, so it holds"


def test_a_paused_run_keeps_its_checkout(rig: DispatchRig) -> None:
    first, second = _two_in_one_checkout(rig)
    rig.tick()

    rig.end_run(
        first, RunOutcome.PAUSED, checkpoint={"kind": "awaits_human", "step": "s"}
    )
    rig.tick()

    assert _launches(rig, second) == 0
    assert rig.status(first) is NodeStatus.BLOCKED_ON_SQ_CHECKPOINT


def test_a_paused_run_with_an_unknown_review_still_holds_its_checkout(
    rig: DispatchRig,
) -> None:
    first, second = _two_in_one_checkout(rig)
    rig.tick()

    rig.end_run(
        first,
        RunOutcome.PAUSED,
        checkpoint={"kind": "awaits_human", "step": "s"},
        **missing_file_review().document,
    )
    rig.tick()

    assert rig.status(first) is NodeStatus.BLOCKED_ON_HUMAN, "told to a person"
    assert _launches(rig, second) == 0


def test_a_slice_in_another_worktree_is_dispatched_meanwhile(
    rig: DispatchRig,
) -> None:
    first = rig.step("first", FIRST_INDEX)
    elsewhere = rig.step("elsewhere", OTHER_WORKTREE_INDEX)
    rig.tick()

    assert _launches(rig, first) == 1
    assert _launches(rig, elsewhere) == 1
    assert sorted(rig.popen.cwds) == sorted(
        [str(rig.world.root), str(rig.world.second)]
    )
