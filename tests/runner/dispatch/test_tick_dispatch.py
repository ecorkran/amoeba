"""Dispatch at tick level: a step is pointed on one tick, launched on the next."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.runner.dispatch.params import (
    MERGE_DISABLED,
    PARAM_MERGE,
    PARAM_MERGE_POLICY,
    PARAM_SLICE,
)
from amoeba.runner.intent.apply import apply_pending_intents
from amoeba.runner.launch import PARAM_PARAMS
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.project_config import MergePolicy, ProjectSettings
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_RUN_ID,
    CommandKind,
    Store,
)
from runner.dispatch.tick_rig import DispatchRig
from runner.intent.intent_support import submit

PROJECT = "demo"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    yield DispatchRig(tmp_path, store)


def test_driven_slice_design_launches_p4_on_the_first_tick(rig: DispatchRig) -> None:
    node = rig.step("run-dispatch", 125)

    rig.tick()

    assert rig.entries(CommandKind.CF_WRITE, node) == [], "no pointer is written"
    [run] = rig.entries(CommandKind.SQ_RUN, node)
    assert not run.is_resolved
    assert run.parameters[PARAM_CHECKOUT] == str(rig.world.root)
    [argv] = rig.popen.argvs
    assert argv[:4] == ["sq", "run", "P4", "125"], "the slice is the target"
    assert str(run.parameters[PARAM_RUN_ID]) in argv
    assert run.parameters[PARAM_PARAMS] == {PARAM_SLICE: "125"}
    assert rig.popen.cwds == [str(rig.world.root)]


def test_implementation_carries_merge_false_under_the_human_policy(
    rig: DispatchRig,
) -> None:
    rig.tick_rig.project_settings = ProjectSettings(merge_policy=MergePolicy.HUMAN)
    rig.step("build-it", 125, LifecycleStep.IMPLEMENTATION)

    rig.tick()

    [argv] = rig.popen.argvs
    assert "P6" in argv
    assert f"{PARAM_MERGE}={MERGE_DISABLED}" in argv


def test_with_no_config_the_p6_entry_records_the_auto_policy(
    rig: DispatchRig,
) -> None:
    node = rig.step("build-it", 125, LifecycleStep.IMPLEMENTATION)

    rig.tick()

    [run] = rig.entries(CommandKind.SQ_RUN, node)
    assert run.parameters[PARAM_MERGE_POLICY] == "auto"
    assert run.parameters[PARAM_PARAMS] == {PARAM_SLICE: "125"}


def test_under_the_auto_policy_p6_runs_without_merge_false_and_records_auto(
    rig: DispatchRig,
) -> None:
    rig.tick_rig.project_settings = ProjectSettings(merge_policy=MergePolicy.AUTO)
    node = rig.step("build-it", 125, LifecycleStep.IMPLEMENTATION)

    rig.tick()

    [run] = rig.entries(CommandKind.SQ_RUN, node)
    assert run.parameters[PARAM_MERGE_POLICY] == "auto"
    assert run.parameters[PARAM_PARAMS] == {PARAM_SLICE: "125"}
    [argv] = rig.popen.argvs
    assert not any(arg.startswith(f"{PARAM_MERGE}=") for arg in argv)


def test_a_planning_launch_records_no_merge_policy(rig: DispatchRig) -> None:
    node = rig.step("run-dispatch", 125)

    rig.tick()

    [run] = rig.entries(CommandKind.SQ_RUN, node)
    assert PARAM_MERGE_POLICY not in run.parameters


def test_a_project_that_is_not_driven_launches_nothing(rig: DispatchRig) -> None:
    submit(rig.store, {"intent": "pause"}, project_id=PROJECT)
    apply_pending_intents(rig.store, PROJECT)
    node = rig.step("held", 125)

    rig.tick()

    assert rig.entries(CommandKind.CF_WRITE, node) == []
    assert rig.entries(CommandKind.SQ_RUN, node) == []
    assert rig.popen.argvs == []


def test_the_second_worktree_launches_in_its_own_checkout(rig: DispatchRig) -> None:
    node = rig.step("second-work", 225)

    rig.tick()

    [run] = rig.entries(CommandKind.SQ_RUN, node)
    assert run.parameters[PARAM_CHECKOUT] == str(rig.world.second)
    assert rig.popen.cwds == [str(rig.world.second)]
    assert rig.entries(CommandKind.CF_WRITE, node) == []
