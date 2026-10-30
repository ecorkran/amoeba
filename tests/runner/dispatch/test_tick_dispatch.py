"""Dispatch at tick level: a driven step launches on the first tick."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.process import RunOutcome
from amoeba.runner.dispatch.params import (
    PARAM_SLICE,
)
from amoeba.runner.intent.apply import apply_pending_intents
from amoeba.runner.launch import PARAM_PARAMS
from amoeba.runner.project_config import ProjectSettings
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_RUN_ID,
    CommandKind,
    Store,
)
from runner.dispatch.tick_rig import PIPELINE, DispatchRig
from runner.intent.intent_support import submit
from runner.resolutions.rig_support import successor_slice

PROJECT = "demo"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    yield DispatchRig(tmp_path, store)


def test_a_driven_slice_launches_the_configured_pipeline_on_the_first_tick(
    rig: DispatchRig,
) -> None:
    node = rig.step("run-dispatch", 125)

    rig.tick()

    assert rig.entries(CommandKind.CF_WRITE, node) == [], "no pointer is written"
    [run] = rig.entries(CommandKind.SQ_RUN, node)
    assert not run.is_resolved
    assert run.parameters[PARAM_CHECKOUT] == str(rig.world.root)
    [argv] = rig.popen.argvs
    assert argv[:4] == ["sq", "run", PIPELINE, "125"], "the slice is the target"
    assert str(run.parameters[PARAM_RUN_ID]) in argv
    assert run.parameters[PARAM_PARAMS] == {PARAM_SLICE: "125"}
    assert rig.popen.cwds == [str(rig.world.root)]


def test_the_projects_params_become_dash_p_arguments(rig: DispatchRig) -> None:
    rig.tick_rig.project_settings = ProjectSettings(
        pipeline="p4567", params={"model": "opus", "effort": "high"}
    )
    node = rig.step("params", 125)

    rig.tick()

    [run] = rig.entries(CommandKind.SQ_RUN, node)
    assert run.parameters[PARAM_PARAMS] == {
        PARAM_SLICE: "125",
        "model": "opus",
        "effort": "high",
    }
    [argv] = rig.popen.argvs
    assert argv[:4] == ["sq", "run", "p4567", "125"]
    assert "model=opus" in argv and "effort=high" in argv
    assert not any(arg.startswith("merge") for arg in argv)


def test_the_next_slice_waits_for_its_predecessor_to_be_done(
    rig: DispatchRig,
) -> None:
    first = rig.step("first", 125)
    second = successor_slice(rig, first)
    rig.tick()
    assert len(rig.entries(CommandKind.SQ_RUN, first)) == 1
    assert rig.entries(CommandKind.SQ_RUN, second) == []

    rig.end_run(first, RunOutcome.COMPLETED)

    assert len(rig.entries(CommandKind.SQ_RUN, second)) == 1


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
