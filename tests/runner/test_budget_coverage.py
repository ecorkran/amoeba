"""No subprocess call starts once the tick budget is spent (D10).

Every subprocess call the tick can make (the poll, a ``cf`` probe, ``Popen``) is
wrapped so that it fails the test if it begins after the deadline. A new call
site that skips ``TickBudget.allows_call`` fails here.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from amoeba.process import RunOutcome
from amoeba.runner.budget import TickResult
from amoeba.runner.cf_call import CfRun
from amoeba.runner.dispatch.observe_pointer import PointerStage
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.git_read import GIT_SUBCOMMANDS
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.runner.lifecycle.human_steps import HumanStepPlanner
from amoeba.runner.resolutions.planner import ContinuationPlanner
from amoeba.store import PARAM_RUN_ID, CommandKind, NodeKind, Store
from runner.dispatch.tick_rig import DispatchRig
from runner.gates.merge_support import implemented
from runner.observe_support import Child, document
from runner.plan_tick_support import serve_plan
from runner.routing.table_support import shipped_table
from runner.tick_support import GRACE, PROJECT, Rig, link

DEADLINE = 5.0
CALL_COST = 2.0


@pytest.fixture
def busy_rig(tmp_path: Path, store: Store) -> Rig:
    """Three confirmed runs due a poll, an unprobed link and two runnable nodes."""
    rig = Rig(tmp_path, store)
    for index in range(3):
        node = store.create_node(
            project_id=PROJECT, kind=NodeKind.SLICE, title=f"running-{index}"
        )
        entry = store.journal_issue(
            node.id,
            kind=CommandKind.SQ_RUN,
            parameters={
                PARAM_PIPELINE: "P4",
                PARAM_PARAMS: {},
                PARAM_RUN_ID: f"run-{index}",
            },
        )
        rig.tracker.track(entry.id, Child(None))
        rig.tracker.confirm(entry.id)
    link(store, "s-1", "cf-1", PROJECT)
    for index in range(2):
        store.create_node(
            project_id=PROJECT, kind=NodeKind.SLICE, title=f"free-{index}"
        )
    return rig


def _guard(rig: Rig, started: list[str]) -> None:
    """Make each call record itself, fail if the deadline passed, and cost time."""

    def call(kind: str) -> None:
        started.append(kind)
        assert rig.clock.seconds < DEADLINE, f"a {kind} call started after the deadline"
        rig.clock.seconds += CALL_COST

    rig.poll.on_call = lambda: call("poll")
    rig.cf.on_call = lambda: call("cf")
    rig.popen.on_call = lambda: call("popen")


def test_no_call_starts_after_the_deadline_while_a_tick_spends_its_budget(
    busy_rig: Rig,
) -> None:
    rig = busy_rig
    rig.deadline = DEADLINE
    rig.poll.answers.extend(
        document(f"run-{i}", RunOutcome.TIMED_OUT) for i in range(3)
    )
    started: list[str] = []
    _guard(rig, started)

    result, _ = rig.tick()

    assert result is TickResult.CUT_OFF
    assert 0 < len(started) <= 3, "the budget let a few calls through, then stopped"


def test_no_call_starts_when_the_budget_is_spent_before_the_tick(
    busy_rig: Rig,
) -> None:
    rig = busy_rig
    rig.deadline = 0.0
    started: list[str] = []
    _guard(rig, started)

    result, tick = rig.tick()

    assert result is TickResult.CUT_OFF and not tick.wrote
    assert started == []
    assert rig.poll.asked == [] and rig.cf.calls == [] and rig.popen.calls == 0


@pytest.mark.parametrize(
    ("deadline", "cf_calls"),
    [
        (4.0, 2),  # status, probe: spent before the plan's initiatives read
        (7.0, 4),  # ... initiatives, slices 100: spent before slices 200
    ],
    ids=["before-the-initiatives-read", "between-slice-reads"],
)
def test_no_plan_read_call_starts_after_the_deadline_and_nothing_is_written(
    tmp_path: Path, store: Store, deadline: float, cf_calls: int
) -> None:
    rig = Rig(tmp_path, store)
    rig.planners = ()
    link(store, "s-1", "cf-1", PROJECT)
    serve_plan(rig.cf, (100, 200), {100: (101,), 200: (201,)})
    rig.deadline = deadline

    def call(kind: str) -> None:
        assert rig.clock.seconds < deadline, f"a {kind} call started after the deadline"
        rig.clock.seconds += CALL_COST

    rig.cf.on_call = lambda: call("cf")
    rig.popen.on_call = lambda: call("popen")

    result, _ = rig.tick()

    assert result is TickResult.CUT_OFF
    assert len(rig.cf.calls) == cf_calls
    assert store.nodes_for_project(PROJECT) == []
    assert store.open_project_escalations(PROJECT) == []


def test_no_pointer_call_starts_after_the_deadline(
    tmp_path: Path, store: Store
) -> None:
    """The dispatch path's ``cf`` calls (the write and its read-back) are budgeted."""
    rig = DispatchRig(tmp_path, store)
    rig.step("first", 125)
    rig.step("second", 225)
    clock = rig.tick_rig.clock
    rig.tick_rig.deadline = DEADLINE
    real = rig.world.run()
    started: list[str] = []

    def guarded(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        started.append(argv[1])
        assert clock.seconds < DEADLINE, f"cf {argv[1]} started after the deadline"
        clock.seconds += CALL_COST
        return real(argv, **kwargs)

    rig.tick_rig.pointers = PointerStage(guarded, 8.0, GRACE, clock.wall)

    rig.tick_rig.tick()

    assert started == ["set", "get", "set"], "the second write's read-back waited"
    unresolved = [e for e in store.journal_entries(PROJECT) if not e.is_resolved]
    assert len(unresolved) == 1, "left for the next tick's observe to read back"


# -- slice 128: the gate, pre-dispatch and merge reads are budgeted too ----------


def test_no_gate_read_starts_after_the_deadline_and_only_allowed_git_runs(
    tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slice from launch to merge observation, with every read guarded (D10).

    The launch is checked (git status), the completed run is observed (cf reads and
    git status), and the merge is observed (the target and ``merge-base``). Each tick
    gets a short budget; a call that starts after its deadline fails the test.
    """
    rig = DispatchRig(tmp_path, store)
    rig.tick_rig.routing_table = shipped_table()
    rig.tick_rig.planners = (
        HumanStepPlanner(),
        DispatchPlanner(),
        ContinuationPlanner(),
    )
    clock = rig.tick_rig.clock
    git_calls: list[list[str]] = []
    cf_calls: list[list[str]] = []

    def guard(real: CfRun) -> CfRun:
        def guarded(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            assert clock.seconds < rig.tick_rig.deadline, f"{argv[:3]} started late"
            clock.seconds += CALL_COST
            (git_calls if argv[0] == "git" else cf_calls).append(argv)
            return real(argv, **kwargs)

        return guarded

    original_tick = rig.tick_rig.tick

    def armed() -> object:
        rig.tick_rig.deadline = clock.seconds + DEADLINE * 4
        return original_tick()

    monkeypatch.setattr(rig.tick_rig, "tick", armed)

    scenario = implemented(rig, wrap_gate_run=guard)
    rig.tick()
    rig.tick()

    assert rig.status(scenario.merge) is not None
    subcommands = [
        next(arg for arg in argv[1:] if not arg.startswith("-")) for argv in git_calls
    ]
    assert set(subcommands) <= GIT_SUBCOMMANDS
    assert "status" in subcommands and "merge-base" in subcommands
    assert any(argv[1] == "status" for argv in cf_calls), "CF's gate was read"
    assert any(argv[1] == "config" for argv in cf_calls), "the target was read"
