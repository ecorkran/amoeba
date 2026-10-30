"""D4 at tick level: one pipeline per checkout, held from the pointer write."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from cf_stub import read_cf_state
from sq_stub_scripts import missing_file_review

from amoeba.process import RunOutcome
from amoeba.runner.intent.apply import apply_pending_intents
from amoeba.store import CommandKind, Node, NodeStatus, Store
from runner.dispatch.tick_rig import DispatchRig
from runner.intent.intent_support import submit

PROJECT = "demo"
FIRST_INDEX = 125
SECOND_INDEX = 126
OTHER_WORKTREE_INDEX = 225


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    yield DispatchRig(tmp_path, store)


def _pointers(rig: DispatchRig, node: Node) -> int:
    return len(rig.entries(CommandKind.CF_WRITE, node))


def _two_in_one_checkout(rig: DispatchRig) -> tuple[Node, Node]:
    first = rig.step("first", FIRST_INDEX)
    second = rig.step("second", SECOND_INDEX)
    return first, second


def test_second_slice_waits_for_checkout(rig: DispatchRig) -> None:
    first, second = _two_in_one_checkout(rig)

    rig.tick()
    assert _pointers(rig, first) == 1 and _pointers(rig, second) == 0, "claimed"

    rig.tick()
    assert rig.entries(CommandKind.SQ_RUN, first), "the first launches"
    assert _pointers(rig, second) == 0, "in flight"

    rig.tick()
    assert _pointers(rig, second) == 0, "still in flight"
    assert rig.popen.argvs and len(rig.popen.argvs) == 1


def test_the_second_slice_is_dispatched_the_tick_the_first_run_completes(
    rig: DispatchRig,
) -> None:
    first, second = _two_in_one_checkout(rig)
    rig.tick()
    rig.tick()
    assert _pointers(rig, second) == 0

    rig.end_run(first, RunOutcome.COMPLETED)

    assert _pointers(rig, second) == 1
    assert len(rig.entries(CommandKind.CF_WRITE, first)) == 1


def test_the_second_slice_is_dispatched_the_tick_the_first_run_fails(
    rig: DispatchRig,
) -> None:
    first, second = _two_in_one_checkout(rig)
    rig.tick()
    rig.tick()

    rig.end_run(
        first,
        RunOutcome.FAILED,
        failure={"kind": "cost_cap", "step": "s", "message": "m"},
    )

    assert rig.status(first) is NodeStatus.BLOCKED_ON_HUMAN
    assert _pointers(rig, second) == 1


def test_a_paused_run_keeps_its_checkout(rig: DispatchRig) -> None:
    first, second = _two_in_one_checkout(rig)
    rig.tick()
    rig.tick()

    rig.end_run(
        first, RunOutcome.PAUSED, checkpoint={"kind": "awaits_human", "step": "s"}
    )
    rig.tick()
    rig.tick()

    assert _pointers(rig, second) == 0
    assert rig.status(first) is NodeStatus.BLOCKED_ON_SQ_CHECKPOINT


def test_a_paused_run_with_an_unknown_review_still_holds_its_checkout(
    rig: DispatchRig,
) -> None:
    first, second = _two_in_one_checkout(rig)
    rig.tick()
    rig.tick()

    rig.end_run(
        first,
        RunOutcome.PAUSED,
        checkpoint={"kind": "awaits_human", "step": "s"},
        **missing_file_review().document,
    )
    rig.tick()

    assert rig.status(first) is NodeStatus.BLOCKED_ON_HUMAN, "told to a person"
    assert _pointers(rig, second) == 0


def test_a_slice_in_another_worktree_is_dispatched_meanwhile(
    rig: DispatchRig,
) -> None:
    first = rig.step("first", FIRST_INDEX)
    elsewhere = rig.step("elsewhere", OTHER_WORKTREE_INDEX)
    rig.tick()
    rig.tick()

    assert len(rig.entries(CommandKind.SQ_RUN, first)) == 1
    assert len(rig.entries(CommandKind.SQ_RUN, elsewhere)) == 1
    assert sorted(rig.popen.cwds) == sorted(
        [str(rig.world.root), str(rig.world.second)]
    )


def test_a_pointed_step_overwritten_while_not_current_writes_again_first(
    rig: DispatchRig,
) -> None:
    slice_node, first = rig.slice_and_step("first", FIRST_INDEX)
    initiative_id = slice_node.parent_id
    assert initiative_id is not None
    rig.tick()
    assert _pointers(rig, first) == 1

    submit(rig.store, {"intent": "pause"}, node_id=initiative_id, project_id=PROJECT)
    apply_pending_intents(rig.store, PROJECT)
    state = read_cf_state(rig.world.state_path)
    state["worktrees"][0]["activeSlice"] = "130-slice.someone-else"
    rig.world.state_path.write_text(json.dumps(state), encoding="utf-8")
    submit(rig.store, {"intent": "resume"}, node_id=initiative_id, project_id=PROJECT)
    apply_pending_intents(rig.store, PROJECT)

    rig.tick()
    assert _pointers(rig, first) == 2, "it writes its pointer again"
    assert rig.entries(CommandKind.SQ_RUN, first) == [], "and does not launch yet"

    rig.tick()
    assert len(rig.entries(CommandKind.SQ_RUN, first)) == 1
