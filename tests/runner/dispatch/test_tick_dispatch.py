"""Dispatch at tick level: a step is pointed on one tick, launched on the next."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cf_stub import (
    GET_QUIRK_ENV,
    SET_MODE_ENV,
    GetQuirk,
    PointerMode,
    read_cf_state,
    write_cf_state,
)

from amoeba.runner.dispatch.params import MERGE_DISABLED, PARAM_MERGE, PARAM_SLICE
from amoeba.runner.faults import PAYLOAD_FAULT_KIND, FaultKind
from amoeba.runner.intent.apply import apply_pending_intents
from amoeba.runner.launch import PARAM_PARAMS
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_EXPECTED_SLICE_INDEX,
    PARAM_RUN_ID,
    Channel,
    CommandKind,
    JournalOutcome,
    NodeStatus,
    Store,
)
from runner.dispatch.pointer_support import STEM
from runner.dispatch.tick_rig import DispatchRig
from runner.intent.intent_support import submit

PROJECT = "demo"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    yield DispatchRig(tmp_path, store)


def test_driven_slice_design_writes_pointer_then_launches_p4(rig: DispatchRig) -> None:
    node = rig.step("run-dispatch", 125)

    rig.tick()

    [pointer] = rig.entries(CommandKind.CF_WRITE, node)
    assert pointer.outcome is JournalOutcome.COMPLETED
    assert pointer.parameters[PARAM_CHECKOUT] == str(rig.world.root)
    assert pointer.parameters[PARAM_EXPECTED_SLICE_INDEX] == 125
    assert rig.entries(CommandKind.SQ_RUN, node) == []
    assert rig.popen.argvs == [], "the launch waits for the next tick"

    rig.tick()

    [run] = rig.entries(CommandKind.SQ_RUN, node)
    assert not run.is_resolved
    assert run.parameters[PARAM_CHECKOUT] == str(rig.world.root)
    [argv] = rig.popen.argvs
    assert argv[:4] == ["sq", "run", "P4", "125"], "the slice is the target"
    assert str(run.parameters[PARAM_RUN_ID]) in argv
    assert run.parameters[PARAM_PARAMS] == {PARAM_SLICE: "125"}
    assert rig.popen.cwds == [str(rig.world.root)]


def test_implementation_carries_merge_false(rig: DispatchRig) -> None:
    rig.step("build-it", 125, LifecycleStep.IMPLEMENTATION)

    rig.tick()
    rig.tick()

    [argv] = rig.popen.argvs
    assert "P6" in argv
    assert f"{PARAM_MERGE}={MERGE_DISABLED}" in argv


def test_a_project_that_is_not_driven_issues_neither(rig: DispatchRig) -> None:
    submit(rig.store, {"intent": "pause"}, project_id=PROJECT)
    apply_pending_intents(rig.store, PROJECT)
    node = rig.step("held", 125)

    rig.tick()
    rig.tick()

    assert rig.entries(CommandKind.CF_WRITE, node) == []
    assert rig.entries(CommandKind.SQ_RUN, node) == []
    assert rig.popen.argvs == []


def test_the_second_worktree_gets_the_write_and_names_the_slice(
    rig: DispatchRig,
) -> None:
    slice_node, node = rig.slice_and_step("second-work", 225)

    rig.tick()

    state = read_cf_state(rig.world.state_path)
    by_id = {w["id"]: w for w in state["worktrees"]}
    assert by_id["wt_b"]["activeSlice"] == "225-slice.second"
    assert "activeSlice" not in by_id["wt_a"]
    [pointer] = rig.entries(CommandKind.CF_WRITE, node)
    assert pointer.parameters[PARAM_CHECKOUT] == str(rig.world.second)
    found = rig.store.get_node(slice_node.id)
    assert found is not None and found.cf.slice_name == "second"


def test_an_already_pointed_checkout_still_launches_on_the_next_tick(
    rig: DispatchRig,
) -> None:
    write_cf_state(
        rig.world.state_path,
        cf_project_id="project_1_abc",
        project_path=rig.world.root,
        worktrees=[
            {
                **rig.world.worktree_entry("wt_a", rig.world.root, 100, 199),
                "activeSlice": STEM,
            },
            rig.world.worktree_entry("wt_b", rig.world.second, 200, 299),
        ],
        slices={125: STEM},
    )
    before = rig.world.state_path.read_bytes()
    node = rig.step("already", 125)

    rig.tick()
    assert rig.world.state_path.read_bytes() == before, "set wrote nothing"
    rig.tick()

    assert len(rig.entries(CommandKind.SQ_RUN, node)) == 1


@pytest.mark.parametrize(
    ("knobs", "fragment"),
    [
        ({SET_MODE_ENV: PointerMode.FAIL.value}, "cf set exited 1"),
        ({GET_QUIRK_ENV: GetQuirk.OTHER_PROJECT_PATH.value}, "answered for"),
        ({GET_QUIRK_ENV: GetQuirk.OTHER_WORKTREE_ID.value}, "worktree"),
    ],
    ids=["cf set fails", "another path", "another worktree"],
)
def test_a_failed_or_misread_pointer_blocks_and_resolves_failed(
    rig: DispatchRig, knobs: dict[str, str], fragment: str
) -> None:
    rig.use_world(knobs)
    node = rig.step("doomed", 125)

    rig.tick()

    [pointer] = rig.entries(CommandKind.CF_WRITE, node)
    assert pointer.outcome is JournalOutcome.FAILED
    assert rig.status(node) is NodeStatus.BLOCKED_ON_HUMAN
    [message] = rig.store.messages(PROJECT, channel=Channel.ESCALATION)
    payload = dict(message.payload or {})
    assert payload[PAYLOAD_FAULT_KIND] == FaultKind.POINTER_WRITE_FAILED.value
    assert fragment in str(payload["reason"])
    rig.tick()
    assert rig.popen.argvs == []


def test_another_index_blocks_and_resolves_failed(rig: DispatchRig) -> None:
    write_cf_state(
        rig.world.state_path,
        cf_project_id="project_1_abc",
        project_path=rig.world.root,
        worktrees=[rig.world.worktree_entry("wt_a", rig.world.root, 100, 199)],
        slices={125: "126-slice.the-wrong-one"},
    )
    node = rig.step("wrong-index", 125)

    rig.tick()

    [pointer] = rig.entries(CommandKind.CF_WRITE, node)
    assert pointer.outcome is JournalOutcome.FAILED
    assert rig.status(node) is NodeStatus.BLOCKED_ON_HUMAN
