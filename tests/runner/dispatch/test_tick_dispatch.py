"""Dispatch at tick level: a driven step launches on the first tick."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.runner.dispatch.params import (
    PARAM_SLICE,
)
from amoeba.runner.intent.apply import apply_pending_intents
from amoeba.runner.launch import PARAM_PARAMS
from amoeba.runner.lifecycle.steps import LifecycleStep
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


def test_implementation_launches_p6_with_only_the_slice(rig: DispatchRig) -> None:
    node = rig.step("build-it", 125, LifecycleStep.IMPLEMENTATION)

    rig.tick()

    [run] = rig.entries(CommandKind.SQ_RUN, node)
    assert run.parameters[PARAM_PARAMS] == {PARAM_SLICE: "125"}
    [argv] = rig.popen.argvs
    assert "P6" in argv
    assert not any(arg.startswith("merge") for arg in argv)
    assert "merge_policy" not in run.parameters and "target" not in run.parameters


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
