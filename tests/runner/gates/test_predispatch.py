"""D5, D6: the branch rule and the entry gate, over every row of both tables."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amoeba.runner.faults import FaultKind
from amoeba.runner.gates.cf_status import CFActiveSlice, parse_status
from amoeba.runner.gates.predispatch import (
    DIRTY_PATHS_SHOWN,
    Block,
    Disagreement,
    NoResult,
    Ok,
    allowed_branches,
    branch_rule,
    entry_gate,
)
from amoeba.runner.git_read import GitStatus
from amoeba.runner.lifecycle.steps import LifecycleStep
from runner.gates.purity import io_use

STATUS_FIXTURES = Path(__file__).parents[2] / "fixtures" / "cf" / "status"
TARGET = "main"
SLICE = 128
OWN = "128-slice.gates-git-and-human-steps"
HEAD = "abc123"


def _git(branch: str | None, *dirty: str) -> GitStatus:
    return GitStatus(branch=branch, head=HEAD, dirty=tuple(dirty))


def _rule(
    status: GitStatus, pipeline: str, *, resume: bool = False, target: str = TARGET
) -> Block | None:
    return branch_rule(status, target, pipeline, SLICE, resume=resume)


@pytest.mark.parametrize("pipeline", ["P4", "P5", "P6"])
def test_a_clean_tree_on_the_target_is_allowed_for_every_pipeline(
    pipeline: str,
) -> None:
    assert _rule(_git("main"), pipeline) is None


def test_dirty_tree_blocks_launch() -> None:
    block = _rule(_git("main", "a.txt", "b.txt"), "P5")

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_DIRTY
    assert block.payload == {"paths": ["a.txt", "b.txt"], "path_count": 2}


def test_only_the_first_twenty_dirty_paths_are_listed_but_all_are_counted() -> None:
    paths = tuple(f"f{i}.txt" for i in range(DIRTY_PATHS_SHOWN + 5))

    block = _rule(_git("main", *paths), "P4")

    assert block is not None
    assert block.payload["paths"] == list(paths[:DIRTY_PATHS_SHOWN])
    assert block.payload["path_count"] == DIRTY_PATHS_SHOWN + 5


def test_resume_not_blocked_by_its_own_dirty_tree() -> None:
    assert _rule(_git("main", "work.txt"), "P6", resume=True) is None
    assert _rule(_git(OWN, "work.txt"), "P6", resume=True) is None


def test_a_resume_is_still_checked_for_its_branch() -> None:
    block = _rule(_git("other-branch", "work.txt"), "P6", resume=True)

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_BRANCH


@pytest.mark.parametrize("pipeline", ["P4", "P5"])
def test_planning_run_refused_off_target(pipeline: str) -> None:
    block = _rule(_git(OWN), pipeline)

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_BRANCH
    assert block.payload["branch"] == OWN
    assert block.payload["target"] == TARGET
    assert block.payload["allowed"] == (TARGET,)
    assert OWN in block.context and TARGET in block.context


def test_p6_is_allowed_on_this_slices_own_branch() -> None:
    assert _rule(_git(OWN), "P6") is None


@pytest.mark.parametrize(
    "branch",
    ["129-slice.another-slice", "feature/x", "128-notslice", "dev/erik/128-slice.x"],
)
def test_p6_blocks_on_another_slices_branch_or_any_other(branch: str) -> None:
    block = _rule(_git(branch), "P6")

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_BRANCH
    assert block.payload["allowed"] == (TARGET, f"{SLICE}-slice.*")


def test_a_slash_prefixed_branch_is_not_the_slices_own() -> None:
    assert _rule(_git(f"dev/{OWN}"), "P6") is not None


def test_detached_head_blocks() -> None:
    block = _rule(_git(None), "P6")

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_BRANCH
    assert block.payload["branch"] is None


def test_an_integration_branch_as_target_blocks_main() -> None:
    block = _rule(_git("main"), "P5", target="dev/erik")

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_BRANCH
    assert _rule(_git("dev/erik"), "P5", target="dev/erik") is None


def test_the_branch_comes_before_the_dirty_tree() -> None:
    block = _rule(_git("other", "a.txt"), "P5")

    assert block is not None and block.fault_kind is FaultKind.CHECKOUT_BRANCH


def test_allowed_branches_by_pipeline() -> None:
    assert allowed_branches("P4", "main", 7) == ("main",)
    assert allowed_branches("P5", "main", 7) == ("main",)
    assert allowed_branches("P6", "main", 7) == ("main", "7-slice.*")


# -- the entry gate ------------------------------------------------------------


def _active(fixture: str, *, index: int = SLICE) -> CFActiveSlice:
    document = json.loads((STATUS_FIXTURES / f"{fixture}.json").read_text())
    document["activeSlice"]["index"] = index
    active = parse_status(document)
    assert active is not None
    return active


def _gate(
    step: LifecycleStep, fixture: str, *, accepted: bool = False, index: int = SLICE
) -> Ok | Block | NoResult | Disagreement:
    return entry_gate(step, _active(fixture, index=index), SLICE, accepted=accepted)


@pytest.mark.parametrize(
    ("step", "fixture"),
    [
        (LifecycleStep.TASKS, "needs_tasks"),
        (LifecycleStep.TASKS, "in_implementation"),
        (LifecycleStep.TASKS, "complete"),
        (LifecycleStep.IMPLEMENTATION, "in_implementation_no_task_done"),
        (LifecycleStep.IMPLEMENTATION, "in_implementation"),
        (LifecycleStep.IMPLEMENTATION, "pending_review_code"),
        (LifecycleStep.IMPLEMENTATION, "complete"),
    ],
)
def test_a_position_past_the_entry_gate_launches(
    step: LifecycleStep, fixture: str
) -> None:
    result = _gate(step, fixture)

    assert isinstance(result, Ok)
    assert result.evidence["gate_status"] == _active(fixture).status


@pytest.mark.parametrize(
    ("step", "fixture"),
    [
        (LifecycleStep.TASKS, "pending_review_slice"),
        (LifecycleStep.TASKS, "review_failed_slice"),
        (LifecycleStep.TASKS, "needs_design"),
        (LifecycleStep.IMPLEMENTATION, "pending_review_tasks"),
        (LifecycleStep.IMPLEMENTATION, "review_failed_tasks"),
        (LifecycleStep.IMPLEMENTATION, "needs_tasks"),
        (LifecycleStep.IMPLEMENTATION, "needs_design"),
        (LifecycleStep.TASKS, "no_active_slice"),
    ],
)
def test_at_or_before_the_entry_gate_blocks_cf_gate_blocks(
    step: LifecycleStep, fixture: str
) -> None:
    result = _gate(step, fixture)

    assert isinstance(result, Block) and result.fault_kind is FaultKind.CF_GATE_BLOCKS
    assert set(result.payload) == {"position", "status", "review_type", "rationale"}


def test_the_block_payload_carries_cf_s_reason() -> None:
    result = _gate(LifecycleStep.TASKS, "review_failed_slice")

    assert isinstance(result, Block)
    assert result.payload["position"] == "AT_SLICE_GATE"
    assert result.payload["review_type"] == "slice"
    assert "FAIL" in str(result.payload["rationale"])


def test_pending_decision_blocks_with_the_decisions() -> None:
    result = _gate(LifecycleStep.TASKS, "pending_decision")

    assert isinstance(result, Block) and result.fault_kind is FaultKind.PENDING_DECISION
    assert result.payload == {"decisions": [{"heading": "Decision", "line": 12}]}


def test_the_decision_gate_comes_before_the_review_gate() -> None:
    result = _gate(LifecycleStep.IMPLEMENTATION, "pending_decision", accepted=True)

    assert isinstance(result, Block) and result.fault_kind is FaultKind.PENDING_DECISION


def test_a_read_about_another_slice_has_no_result() -> None:
    assert isinstance(_gate(LifecycleStep.TASKS, "needs_tasks", index=999), NoResult)


@pytest.mark.parametrize(
    ("step", "fixture"),
    [
        (LifecycleStep.TASKS, "review_failed_slice"),
        (LifecycleStep.TASKS, "pending_review_slice"),
        (LifecycleStep.IMPLEMENTATION, "review_failed_tasks"),
    ],
)
def test_cf_failing_a_pm_accepted_predecessor_is_a_disagreement_not_a_block(
    step: LifecycleStep, fixture: str
) -> None:
    result = _gate(step, fixture, accepted=True)

    assert isinstance(result, Disagreement)
    assert isinstance(result.ok, Ok)
    assert result.gate.status == _active(fixture).status


def test_an_accept_does_not_excuse_a_position_before_the_entry_gate() -> None:
    result = _gate(LifecycleStep.IMPLEMENTATION, "needs_design", accepted=True)

    assert isinstance(result, Block)


def test_an_unknown_position_blocks_even_when_accepted() -> None:
    result = _gate(LifecycleStep.TASKS, "no_active_slice", accepted=True)

    assert isinstance(result, Block) and result.fault_kind is FaultKind.CF_GATE_BLOCKS


def test_slice_design_has_no_entry_gate() -> None:
    with pytest.raises(ValueError, match="no entry gate"):
        _gate(LifecycleStep.SLICE_DESIGN, "needs_design")


def test_the_module_does_no_io() -> None:
    import amoeba.runner.gates.predispatch as module

    assert io_use(module) == []
