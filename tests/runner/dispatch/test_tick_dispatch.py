"""Dispatch at tick level: a driven step launches on the first tick."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

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
    Channel,
    CommandKind,
    NodeStatus,
    Store,
)
from runner.dispatch.tick_rig import PIPELINE, DispatchRig
from runner.intent.intent_support import submit
from runner.observe_support import Child, document
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


# -- slice 132, D11: a project with no pipeline, and a pipeline Squadron lacks ----


def test_a_driven_slice_in_an_unconfigured_project_launches_nothing_and_escalates(
    rig: DispatchRig,
) -> None:
    rig.tick_rig.project_settings = ProjectSettings()
    node = rig.step("unconfigured", 125)

    rig.tick()
    rig.tick()

    assert rig.entries(CommandKind.SQ_RUN, node) == [] and rig.popen.argvs == []
    escalations = rig.store.open_project_escalations(PROJECT)
    assert [m.fault_kind for m in escalations] == ["pipeline_unconfigured"]


def test_the_escalation_closes_once_the_project_is_configured(
    rig: DispatchRig,
) -> None:
    rig.tick_rig.project_settings = ProjectSettings()
    node = rig.step("late-config", 125)
    rig.tick()
    assert len(rig.store.open_project_escalations(PROJECT)) == 1

    rig.tick_rig.project_settings = ProjectSettings(pipeline=PIPELINE)
    rig.tick()

    assert rig.store.open_project_escalations(PROJECT) == []
    assert len(rig.entries(CommandKind.SQ_RUN, node)) == 1


def test_the_escalation_closes_once_the_slice_is_no_longer_driven(
    rig: DispatchRig,
) -> None:
    rig.tick_rig.project_settings = ProjectSettings()
    rig.step("paused-later", 125)
    rig.tick()
    assert len(rig.store.open_project_escalations(PROJECT)) == 1

    submit(rig.store, {"intent": "pause"}, project_id=PROJECT)
    rig.tick()

    assert rig.store.open_project_escalations(PROJECT) == []


def test_a_pipeline_squadron_does_not_have_blocks_only_that_slice(
    rig: DispatchRig,
) -> None:
    def missing(argv: list[str], **kwargs: Any) -> Child | None:
        if kwargs["cwd"] != str(rig.world.root):
            return None  # the other checkout launches normally
        kwargs["stderr"].write(b"Error: Pipeline 'p456' not found.\n")
        return Child(1)

    rig.popen.delegate = missing
    broken = rig.step("broken", 125)
    elsewhere = rig.step("elsewhere", 225)

    rig.tick()
    first, second = (rig.run_of(broken), rig.run_of(elsewhere))
    # The next tick polls both launches, oldest first: no state for the failed one.
    rig.tick_rig.poll.answers += [
        document(str(first.parameters[PARAM_RUN_ID]), RunOutcome.NOT_FOUND),
        document(str(second.parameters[PARAM_RUN_ID]), RunOutcome.TIMED_OUT),
    ]
    rig.tick()

    assert rig.status(broken) is NodeStatus.BLOCKED_ON_HUMAN
    [message] = rig.store.messages(PROJECT, channel=Channel.ESCALATION)
    assert "Pipeline 'p456' not found" in str(message.payload)
    assert len(rig.entries(CommandKind.SQ_RUN, elsewhere)) == 1
    assert rig.status(elsewhere) is NodeStatus.RUNNABLE
