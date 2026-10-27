"""D9 at tick level: merges observed in a real checkout, and what that does."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from cf_stub_gates import CONFIG_MODE_ENV, STATUS_POINTER_ENV, GateMode

from amoeba.runner.cf_call import CfRun
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.faults import PAYLOAD_FAULT_KIND, Fault, FaultKind
from amoeba.runner.gates.merge import (
    PendingMerge,
    _completed_implementation_run,  # pyright: ignore[reportPrivateUsage]
    _observe_one,  # pyright: ignore[reportPrivateUsage]
)
from amoeba.runner.lifecycle.human_steps import HumanStepPlanner
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.project_config import MergePolicy, ProjectSettings
from amoeba.runner.resolutions.planner import ContinuationPlanner
from amoeba.store import (
    BlockedKind,
    Channel,
    CommandKind,
    NodeStatus,
    Store,
)
from runner.dispatch.pointer_support import generous_budget
from runner.dispatch.tick_rig import DispatchRig
from runner.gate_rig import STATUS_FIXTURES, config_knobs
from runner.gates.merge_support import BRANCH, Scenario, implemented
from runner.git_repo import (
    commit_file,
    delete_branch,
    git,
    head_of,
    merge_branch,
    switch,
)
from runner.resolutions.resolution_support import resolve_block
from runner.resolutions.rig_support import INDEX
from runner.routing.table_support import shipped_table

PROJECT = "demo"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    built = DispatchRig(tmp_path, store)
    # These tests exercise the human merge; the auto ones set their own policy.
    built.tick_rig.project_settings = ProjectSettings(merge_policy=MergePolicy.HUMAN)
    built.tick_rig.planners = (
        HumanStepPlanner(),
        DispatchPlanner(),
        ContinuationPlanner(),
    )
    built.tick_rig.routing_table = shipped_table()
    yield built


def _merge_status(rig: DispatchRig, scenario: Scenario) -> NodeStatus:
    return rig.status(scenario.merge)


def _pm_merges(rig: DispatchRig) -> None:
    root = rig.world.root
    switch(root, "main")
    merge_branch(root, BRANCH)


def test_under_human_the_merge_step_blocks_after_p6(rig: DispatchRig) -> None:
    scenario = implemented(rig)

    rig.tick()

    assert _merge_status(rig, scenario) is NodeStatus.BLOCKED_ON_HUMAN
    state = rig.store.blocked_state_for(scenario.merge.id)
    assert state is not None and state.kind is BlockedKind.HUMAN


def test_a_no_ff_merge_completes_the_step_and_resolves_its_block_by_runner(
    rig: DispatchRig,
) -> None:
    scenario = implemented(rig)
    rig.tick()
    assert _merge_status(rig, scenario) is NodeStatus.BLOCKED_ON_HUMAN

    _pm_merges(rig)
    rig.tick()

    assert _merge_status(rig, scenario) is NodeStatus.DONE
    state = rig.store.blocked_state_for(scenario.merge.id, include_resolved=True)
    assert state is not None and state.resolution is not None
    assert state.resolution.resolved_by == "runner"
    assert state.resolution.detail == f"observed: {scenario.head} reachable from main"


def test_merge_observed_after_branch_deleted(rig: DispatchRig) -> None:
    scenario = implemented(rig)
    rig.tick()
    _pm_merges(rig)
    delete_branch(rig.world.root, BRANCH)

    rig.tick()

    assert _merge_status(rig, scenario) is NodeStatus.DONE


def test_a_fix_up_commit_before_the_merge_is_still_observed(rig: DispatchRig) -> None:
    scenario = implemented(rig)
    rig.tick()
    commit_file(rig.world.root, "fixup.txt", "fix\n", "the PM's fix-up")

    _pm_merges(rig)
    rig.tick()

    assert head_of(rig.world.root) != scenario.head
    assert _merge_status(rig, scenario) is NodeStatus.DONE


def test_a_squash_merge_is_not_observed(rig: DispatchRig) -> None:
    scenario = implemented(rig)
    rig.tick()
    root = rig.world.root
    switch(root, "main")
    git(root, "merge", "--squash", BRANCH)
    git(root, "commit", "-q", "-m", "squash the slice")

    rig.tick()

    assert _merge_status(rig, scenario) is NodeStatus.BLOCKED_ON_HUMAN


def test_auto_merge_step_never_blocked(rig: DispatchRig) -> None:
    rig.tick_rig.project_settings = ProjectSettings(merge_policy=MergePolicy.AUTO)
    scenario = implemented(rig, auto_merged=True)

    rig.tick()

    assert _merge_status(rig, scenario) is NodeStatus.DONE
    assert rig.store.blocked_state_for(scenario.merge.id, include_resolved=True) is None


def test_a_human_entry_that_ended_on_the_target_is_unobservable(
    rig: DispatchRig,
) -> None:
    scenario = implemented(rig, own_branch=False)

    rig.tick()

    assert _merge_status(rig, scenario) is NodeStatus.BLOCKED_ON_HUMAN
    payloads = [
        dict(m.payload or {})
        for m in rig.store.messages(PROJECT, channel=Channel.ESCALATION)
    ]
    assert any(p.get("merge_observation") == "unobservable" for p in payloads)
    assert any("nothing was left to merge" in str(p.get("reason")) for p in payloads)


def test_a_failed_read_blocks_nothing_and_closes_once_a_read_succeeds(
    rig: DispatchRig, tmp_path: Path
) -> None:
    scenario = implemented(rig)
    working = rig.tick_rig.gate_run
    rig.tick_rig.gate_run = rig.world.run(
        {
            STATUS_POINTER_ENV: str(STATUS_FIXTURES / "complete.json"),
            CONFIG_MODE_ENV: GateMode.FAIL.value,
            **config_knobs(tmp_path, {}),
        }
    )

    rig.tick()

    assert _merge_status(rig, scenario) is NodeStatus.RUNNABLE, "not blocked"
    [fault] = rig.store.open_project_escalations(PROJECT)
    assert fault.fault_kind == "checkout_read_failed"
    assert str(dict(fault.payload or {})["command"]).startswith("cf config get")

    rig.tick_rig.gate_run = working
    rig.tick()

    assert _merge_status(rig, scenario) is NodeStatus.BLOCKED_ON_HUMAN
    assert rig.store.open_project_escalations(PROJECT) == []


def test_a_later_slices_p4_in_the_checkout_blocks_until_the_merge(
    rig: DispatchRig,
) -> None:
    scenario = implemented(rig)
    rig.tick()
    later = rig.step("later", 126, LifecycleStep.SLICE_DESIGN)
    rig.tick()  # its pointer write

    rig.tick()  # checked on the slice branch: blocked

    assert rig.status(later) is NodeStatus.BLOCKED_ON_HUMAN
    [message] = [
        m
        for m in rig.store.messages(PROJECT, channel=Channel.ESCALATION)
        if dict(m.payload or {}).get(PAYLOAD_FAULT_KIND) == "checkout_branch"
    ]
    assert dict(message.payload or {})["branch"] == BRANCH

    _pm_merges(rig)
    state = rig.store.blocked_state_for(later.id)
    assert state is not None
    resolve_block(rig.store, state.id, "rerun", project_id=PROJECT)
    rig.tick()  # acknowledged, and the merge observed
    rig.tick()  # pointer written again, then checked on the target

    assert _merge_status(rig, scenario) is NodeStatus.DONE
    assert rig.entries(CommandKind.SQ_RUN, later), "launched once the merge landed"


def test_a_spent_budget_starts_no_merge_read(rig: DispatchRig) -> None:
    calls: list[list[str]] = []

    def count(real: CfRun) -> CfRun:
        def counted(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            return real(argv, **kwargs)

        return counted

    scenario = implemented(rig, wrap_gate_run=count)
    calls.clear()
    rig.tick_rig.deadline = 0.0

    rig.tick()

    assert calls == [], "no cf or git call starts once the budget is spent"
    assert _merge_status(rig, scenario) is NodeStatus.RUNNABLE


def test_a_slice_without_a_cf_project_is_a_read_fault_not_an_empty_project(
    rig: DispatchRig,
) -> None:
    scenario = implemented(rig)
    entry = _completed_implementation_run(rig.store, PROJECT, scenario.implementation)
    projectless = replace(
        scenario.slice_node, cf=replace(scenario.slice_node.cf, project=None)
    )
    pending = PendingMerge(projectless, scenario.implementation, scenario.merge, INDEX)

    result = _observe_one(
        pending, entry, generous_budget(), rig.tick_rig.gate_run, 20.0
    )

    assert isinstance(result, Fault)
    assert result.kind is FaultKind.CHECKOUT_READ_FAILED
    assert "no CF project" in result.detail
