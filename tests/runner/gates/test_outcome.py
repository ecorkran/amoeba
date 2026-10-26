"""D2, D3: the observation taken when a run completes, and the gate state it gives."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from cf_stub import PLAN_DIR_ENV, write_cf_stub
from cf_stub_gates import CONFIG_MODE_ENV, STATUS_MODE_ENV, GateMode

from amoeba.runner.budget import TickBudget
from amoeba.runner.gates.cf_status import GatePosition
from amoeba.runner.gates.checks import RunnerCheck
from amoeba.runner.gates.outcome import observe_outcome
from amoeba.runner.gates.outcome_record import (
    FAILURE,
    GATE_POSITION,
    GATE_STATUS,
    OBS_DESIGN_PATH,
    OBS_GATE,
    OBS_GIT,
    GateRead,
    OutcomeObservation,
    ReadFailed,
    gate_state_at_exit,
)
from amoeba.runner.ingest.record import RESULT_CHECK_IDS, RESULT_OUTCOME_OBSERVATION
from amoeba.runner.lifecycle.plan_read import CF_KEY_REVIEW_GATE_EFFECTIVE_DATE
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import CFReference, CommandKind, Node, NodeKind, NodeStatus
from amoeba.store.check_models import check_standing
from runner.dispatch.dispatch_support import entry
from runner.dispatch.pointer_support import budget_allowing, generous_budget
from runner.gate_rig import (
    config_knobs,
    git_checkout,
    single_status_knobs,
    status_fixture,
    write_design,
    write_slice_list,
)
from runner.git_repo import head_of

DESIGN = "project-documents/user/slices/128-slice.gates.md"
SLICE_INDEX = 128
INITIATIVE = 120
TIMEOUT = 20.0
VERSION = "amoeba-test"


class World:
    """A real git checkout with a design, the stub ``cf`` on PATH, and its knobs."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.checkout = git_checkout(tmp_path / "checkout")
        write_design(self.checkout, DESIGN)
        bin_dir = write_cf_stub(tmp_path / "bin")
        monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
        self.set_knobs(
            write_slice_list(tmp_path / "plan", INITIATIVE, {SLICE_INDEX: DESIGN})
        )
        self.status("pending_review_slice")

    def set_knobs(self, knobs: dict[str, str]) -> None:
        for name, value in knobs.items():
            self.monkeypatch.setenv(name, value)

    def status(self, captured: str, slice_index: int = SLICE_INDEX) -> None:
        fixture = status_fixture(self.tmp_path / "status.json", captured, slice_index)
        self.set_knobs(single_status_knobs(fixture))

    def effective_date(self, value: str) -> None:
        self.set_knobs(
            config_knobs(self.tmp_path, {CF_KEY_REVIEW_GATE_EFFECTIVE_DATE: value})
        )

    def observe(
        self,
        step: LifecycleStep = LifecycleStep.SLICE_DESIGN,
        budget: TickBudget | None = None,
    ) -> OutcomeObservation | None:
        node = Node(
            id="slice-node",
            project_id="demo",
            kind=NodeKind.SLICE,
            status=NodeStatus.RUNNABLE,
            title="slice",
            cf=CFReference(project="cf-a", index=SLICE_INDEX),
        )
        run_entry = entry(CommandKind.SQ_RUN, "step-node", self.checkout)
        return observe_outcome(
            run_entry,
            step,
            node,
            INITIATIVE,
            budget or generous_budget(),
            subprocess.run,
            TIMEOUT,
            VERSION,
        )


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    return World(tmp_path, monkeypatch)


def _standings(observation: OutcomeObservation) -> list[str]:
    return [
        check_standing(check.outcome, check.examined_count).value
        for check in observation.checks
    ]


def test_each_read_lands_in_the_observation(world: World) -> None:
    observation = world.observe()

    assert observation is not None
    assert isinstance(observation.gate, GateRead)
    assert observation.gate.position is GatePosition.AT_SLICE_GATE
    assert observation.gate.index == SLICE_INDEX
    assert observation.design_path == DESIGN
    assert observation.design_failure is None
    assert observation.git is None
    assert _standings(observation) == ["passed", "passed"]


def _stored(observation: OutcomeObservation | None) -> dict[str, Any]:
    assert observation is not None
    stored: dict[str, Any] = observation.to_result()[RESULT_OUTCOME_OBSERVATION]  # pyright: ignore[reportAssignmentType]
    return stored


def test_git_is_read_only_for_implementation(world: World) -> None:
    for_tasks = _stored(world.observe(LifecycleStep.TASKS))
    for_code = _stored(world.observe(LifecycleStep.IMPLEMENTATION))

    assert OBS_GIT not in for_tasks
    assert for_code[OBS_GIT] == {"branch": "main", "head": head_of(world.checkout)}


def test_the_result_has_the_observation_and_the_two_check_ids(world: World) -> None:
    observation = world.observe()
    stored = _stored(observation)

    assert stored[OBS_GATE][GATE_POSITION] == "AT_SLICE_GATE"
    assert stored[OBS_GATE][GATE_STATUS] == "pending-review"
    assert stored[OBS_DESIGN_PATH] == DESIGN
    assert observation is not None
    ids = observation.to_result()[RESULT_CHECK_IDS]
    assert ids == [check.id for check in observation.checks]
    assert [str(i).split("-", 3)[3] for i in ids] == [  # type: ignore[union-attr]
        RunnerCheck.UNGATE_REVIEW_NONE.value,
        RunnerCheck.UNGATE_EFFECTIVE_DATE.value,
    ]


def test_a_failed_gate_read_is_recorded_not_raised(world: World) -> None:
    world.monkeypatch.setenv(STATUS_MODE_ENV, GateMode.FAIL.value)

    observation = world.observe()

    assert observation is not None
    assert isinstance(observation.gate, ReadFailed)
    assert _stored(observation)[OBS_GATE].keys() == {FAILURE}


def test_a_gate_read_for_another_slice_is_a_gate_failure(world: World) -> None:
    world.status("pending_review_slice", slice_index=999)

    observation = world.observe()

    assert observation is not None
    assert isinstance(observation.gate, ReadFailed)
    assert (
        "999" in observation.gate.reason and str(SLICE_INDEX) in observation.gate.reason
    )


def test_a_slice_list_without_the_slice_leaves_the_design_unknown(
    world: World,
) -> None:
    world.set_knobs(write_slice_list(world.tmp_path / "plan2", INITIATIVE, {}))
    world.monkeypatch.setenv(PLAN_DIR_ENV, str(world.tmp_path / "plan2"))

    observation = world.observe()

    assert observation is not None
    assert observation.design_path is None
    assert observation.design_failure is not None
    assert _standings(observation) == ["vacuous", "vacuous"]


def test_a_design_file_that_is_not_there_is_vacuous_not_a_pass(world: World) -> None:
    (world.checkout / DESIGN).unlink()

    observation = world.observe()

    assert observation is not None
    assert observation.design_path == DESIGN
    assert observation.design_failure == "the design file is missing"
    assert _standings(observation) == ["vacuous", "vacuous"]


def test_a_failed_config_read_errors_the_effective_date_check(world: World) -> None:
    world.monkeypatch.setenv(CONFIG_MODE_ENV, GateMode.FAIL.value)

    observation = world.observe()

    assert observation is not None
    assert _standings(observation) == ["passed", "errored"]


def test_both_hatches_are_found_in_the_design(world: World) -> None:
    write_design(world.checkout, DESIGN, {"review": "none", "dateCreated": "20200101"})
    world.effective_date("20261020")

    observation = world.observe()

    assert observation is not None
    assert _standings(observation) == ["failed", "failed"]


def test_a_checkout_that_is_not_a_repository_records_a_git_failure(
    world: World,
) -> None:
    world.monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(world.tmp_path))
    bare = world.tmp_path / "not-a-repo"
    bare.mkdir()
    write_design(bare, DESIGN)
    world.checkout = bare

    observation = world.observe(LifecycleStep.IMPLEMENTATION)

    assert observation is not None
    assert isinstance(observation.git, ReadFailed)


def test_a_cut_off_between_the_reads_returns_none(world: World) -> None:
    for calls in range(0, 3):
        assert world.observe(budget=budget_allowing(calls)) is None


def test_a_slice_node_without_cf_coordinates_is_unobservable(world: World) -> None:
    node = Node(
        id="n",
        project_id="demo",
        kind=NodeKind.SLICE,
        status=NodeStatus.RUNNABLE,
        title="s",
    )
    run_entry = entry(CommandKind.SQ_RUN, "step", world.checkout)

    observation = observe_outcome(
        run_entry,
        LifecycleStep.TASKS,
        node,
        1,
        generous_budget(),
        subprocess.run,
        1.0,
        VERSION,
    )

    assert observation is not None
    assert isinstance(observation.gate, ReadFailed)
    assert "no CF project or index" in observation.gate.reason
    assert _standings(observation) == ["vacuous", "errored"]


def _record(position: GatePosition, status: str) -> dict[str, object]:
    return {GATE_POSITION: position.name, GATE_STATUS: status}


@pytest.mark.parametrize(
    ("step", "record", "expected"),
    [
        (
            LifecycleStep.SLICE_DESIGN,
            _record(GatePosition.AT_SLICE_GATE, "pending-review"),
            "pending_review",
        ),
        (
            LifecycleStep.SLICE_DESIGN,
            _record(GatePosition.AT_SLICE_GATE, "review-failed"),
            "review_failed",
        ),
        (
            LifecycleStep.SLICE_DESIGN,
            _record(GatePosition.PAST_SLICE_GATE, "needs-tasks"),
            "clear",
        ),
        (
            LifecycleStep.SLICE_DESIGN,
            _record(GatePosition.NEEDS_DESIGN, "needs-design"),
            "misplaced",
        ),
        (
            LifecycleStep.SLICE_DESIGN,
            _record(GatePosition.PAST_TASKS_GATE, "in-implementation"),
            "misplaced",
        ),
        (
            LifecycleStep.TASKS,
            _record(GatePosition.AT_TASKS_GATE, "pending-review"),
            "pending_review",
        ),
        (
            LifecycleStep.TASKS,
            _record(GatePosition.AT_TASKS_GATE, "review-failed"),
            "review_failed",
        ),
        (
            LifecycleStep.TASKS,
            _record(GatePosition.PAST_TASKS_GATE, "in-implementation"),
            "clear",
        ),
        (
            LifecycleStep.TASKS,
            _record(GatePosition.PAST_SLICE_GATE, "needs-tasks"),
            "misplaced",
        ),
        (
            LifecycleStep.IMPLEMENTATION,
            _record(GatePosition.AT_CODE_GATE, "pending-review"),
            "pending_review",
        ),
        (
            LifecycleStep.IMPLEMENTATION,
            _record(GatePosition.AT_CODE_GATE, "review-failed"),
            "review_failed",
        ),
        (
            LifecycleStep.IMPLEMENTATION,
            _record(GatePosition.PAST_CODE_GATE, "complete"),
            "clear",
        ),
        (
            LifecycleStep.IMPLEMENTATION,
            _record(GatePosition.PAST_TASKS_GATE, "in-implementation"),
            "misplaced",
        ),
        (
            LifecycleStep.TASKS,
            _record(GatePosition.PENDING_DECISION, "pending-decision"),
            "pending_decision",
        ),
        (
            LifecycleStep.TASKS,
            _record(GatePosition.UNKNOWN, "no-active-slice"),
            "unknown",
        ),
        (LifecycleStep.TASKS, {FAILURE: "cf exited 1"}, "unknown"),
        (LifecycleStep.TASKS, {GATE_POSITION: "NOT_A_POSITION"}, "unknown"),
        (LifecycleStep.TASKS, {}, "unknown"),
        (LifecycleStep.TASKS, None, "unknown"),
    ],
)
def test_gate_state_at_exit_follows_d3(
    step: LifecycleStep, record: dict[str, object] | None, expected: str
) -> None:
    assert gate_state_at_exit(step, record) == expected


@pytest.mark.parametrize(
    "step", [LifecycleStep.ARCHITECTURE, LifecycleStep.MERGE, LifecycleStep.SLICE_PLAN]
)
def test_a_step_without_an_exit_gate_is_refused(step: LifecycleStep) -> None:
    with pytest.raises(ValueError, match="no exit gate"):
        gate_state_at_exit(step, None)
