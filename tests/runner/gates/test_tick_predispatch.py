"""D5, D6, D11 at tick level: what the checks do to launches, reissues and resumes."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from cf_stub_gates import STATUS_MODE_ENV, STATUS_POINTER_ENV, GateMode

from amoeba.process import RunOutcome
from amoeba.runner.dispatch.params import PARAM_DISPATCH_CHECK, PARAM_TARGET
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.faults import PAYLOAD_FAULT_KIND
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.runner.lifecycle.plan_read import CF_KEY_INTEGRATION_BRANCH
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.resolutions.planner import ContinuationPlanner
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_CONTINUATION,
    PARAM_RUN_ID,
    BlockedKind,
    Channel,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
    Node,
    Store,
)
from runner.dispatch.tick_rig import DispatchRig
from runner.gate_rig import STATUS_FIXTURES, config_knobs
from runner.git_repo import commit_file, detach_head, head_of, make_branch
from runner.observe_support import document
from runner.resolutions.resolution_support import resolve_block
from runner.resolutions.rig_support import (
    INDEX,
    LOOP_CHECKPOINT,
    answer_poll,
    write_review,
)

PROJECT = "demo"
OLD_RUN_ID = "amoeba-20261024T000000Z-aaaaaaaaaaaa"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    built = DispatchRig(tmp_path, store)
    built.tick_rig.planners = (DispatchPlanner(), ContinuationPlanner())
    yield built


def _gates(
    rig: DispatchRig,
    tmp_path: Path,
    *,
    status: str = "in_implementation",
    config: dict[str, str] | None = None,
    mode: GateMode | None = None,
) -> None:
    """Point the tick's gate reads at the stub: where CF stands, and its config."""
    knobs = {
        STATUS_POINTER_ENV: str(STATUS_FIXTURES / f"{status}.json"),
        **config_knobs(tmp_path, config or {}),
    }
    if mode is not None:
        knobs[STATUS_MODE_ENV] = mode.value
    rig.tick_rig.gate_run = rig.world.run(knobs)


def _dirty(rig: DispatchRig) -> None:
    (rig.world.root / "README.md").write_text("changed\n")


def _step(
    rig: DispatchRig, step: LifecycleStep = LifecycleStep.TASKS, index: int = INDEX
) -> Node:
    node = rig.step("checked", index, step)
    rig.tick()  # the pointer write
    return node


def _block_payload(rig: DispatchRig) -> dict[str, object]:
    [message] = rig.store.messages(PROJECT, channel=Channel.ESCALATION)
    return dict(message.payload or {})


def _blocked_on_human(rig: DispatchRig, node: Node) -> bool:
    state = rig.store.blocked_state_for(node.id)
    return state is not None and state.kind is BlockedKind.HUMAN


def _launched(rig: DispatchRig, node: Node) -> JournalEntry:
    [run] = rig.entries(CommandKind.SQ_RUN, node)
    return run


def _evidence(entry: JournalEntry) -> dict[str, object]:
    check = entry.parameters[PARAM_DISPATCH_CHECK]
    assert isinstance(check, dict)
    return cast("dict[str, object]", check)


# -- the git rules -------------------------------------------------------------


def test_a_dirty_tree_blocks_a_pointed_step_with_the_paths_and_launches_nothing(
    rig: DispatchRig,
) -> None:
    node = _step(rig)
    _dirty(rig)

    rig.tick()

    assert _blocked_on_human(rig, node)
    payload = _block_payload(rig)
    assert payload[PAYLOAD_FAULT_KIND] == "checkout_dirty"
    assert payload["paths"] == ["README.md"] and payload["path_count"] == 1
    assert rig.entries(CommandKind.SQ_RUN, node) == []
    assert rig.popen.argvs == []


def test_a_checkout_on_the_wrong_branch_blocks_a_planning_launch(
    rig: DispatchRig,
) -> None:
    node = _step(rig, LifecycleStep.SLICE_DESIGN)
    make_branch(rig.world.root, "feature-x")

    rig.tick()

    assert _blocked_on_human(rig, node)
    payload = _block_payload(rig)
    assert payload[PAYLOAD_FAULT_KIND] == "checkout_branch"
    assert payload["branch"] == "feature-x" and payload["target"] == "main"
    assert rig.popen.argvs == []


def test_a_detached_head_blocks(rig: DispatchRig) -> None:
    node = _step(rig, LifecycleStep.SLICE_DESIGN)
    detach_head(rig.world.root)

    rig.tick()

    assert _blocked_on_human(rig, node)
    payload = _block_payload(rig)
    assert payload[PAYLOAD_FAULT_KIND] == "checkout_branch"
    assert payload["branch"] is None


def test_an_integration_branch_in_cf_config_makes_main_block_a_planning_launch(
    rig: DispatchRig, tmp_path: Path
) -> None:
    node = _step(rig, LifecycleStep.SLICE_DESIGN)
    _gates(rig, tmp_path, config={CF_KEY_INTEGRATION_BRANCH: "dev/erik"})

    rig.tick()

    assert _blocked_on_human(rig, node)
    payload = _block_payload(rig)
    assert payload[PAYLOAD_FAULT_KIND] == "checkout_branch"
    assert payload["target"] == "dev/erik" and payload["branch"] == "main"


def test_a_p6_launch_on_a_foreign_branch_blocks_and_on_its_own_branch_launches(
    rig: DispatchRig,
) -> None:
    node = _step(rig, LifecycleStep.IMPLEMENTATION)
    make_branch(rig.world.root, "feature-x")
    rig.tick()
    assert _blocked_on_human(rig, node)

    other = rig.step("own", 126, LifecycleStep.IMPLEMENTATION)
    rig.tick()  # its pointer write
    make_branch(rig.world.root, f"126-slice.{'own'}")
    rig.tick()

    assert len(rig.entries(CommandKind.SQ_RUN, other)) == 1
    assert rig.entries(CommandKind.SQ_RUN, node) == []


# -- the entry gate ------------------------------------------------------------


def test_pending_decision_blocks(rig: DispatchRig, tmp_path: Path) -> None:
    node = _step(rig)
    _gates(rig, tmp_path, status="pending_decision")

    rig.tick()

    assert _blocked_on_human(rig, node)
    payload = _block_payload(rig)
    assert payload[PAYLOAD_FAULT_KIND] == "pending_decision"
    assert payload["decisions"] == [{"heading": "Decision", "line": 12}]
    assert rig.popen.argvs == []


@pytest.mark.parametrize(
    ("step", "status"),
    [
        (LifecycleStep.TASKS, "review_failed_slice"),
        (LifecycleStep.TASKS, "pending_review_slice"),
        (LifecycleStep.IMPLEMENTATION, "review_failed_tasks"),
        (LifecycleStep.IMPLEMENTATION, "needs_tasks"),
    ],
)
def test_a_failing_entry_gate_blocks_cf_gate_blocks(
    rig: DispatchRig, tmp_path: Path, step: LifecycleStep, status: str
) -> None:
    node = _step(rig, step)
    _gates(rig, tmp_path, status=status)

    rig.tick()

    assert _blocked_on_human(rig, node)
    payload = _block_payload(rig)
    assert payload[PAYLOAD_FAULT_KIND] == "cf_gate_blocks"
    assert payload["status"] and "rationale" in payload
    assert rig.popen.argvs == []


def test_a_position_past_the_entry_gate_launches(
    rig: DispatchRig, tmp_path: Path
) -> None:
    node = _step(rig)
    _gates(rig, tmp_path, status="needs_tasks")

    rig.tick()

    assert not _blocked_on_human(rig, node)
    assert _evidence(_launched(rig, node))["gate_status"] == "needs-tasks"


# -- evidence on the launch ----------------------------------------------------


def test_a_launch_entry_records_what_the_check_found(rig: DispatchRig) -> None:
    node = _step(rig)

    rig.tick()

    evidence = _evidence(_launched(rig, node))
    assert evidence == {
        "branch": "main",
        "head": head_of(rig.world.root),
        "target": "main",
        "gate_status": "in-implementation",
        "gate_review_type": None,
    }


def test_a_p6_entry_records_main_as_its_target(rig: DispatchRig) -> None:
    node = _step(rig, LifecycleStep.IMPLEMENTATION)

    rig.tick()

    assert _launched(rig, node).parameters[PARAM_TARGET] == "main"


def test_a_p6_entry_records_the_integration_branch_when_one_is_set(
    rig: DispatchRig, tmp_path: Path
) -> None:
    node = _step(rig, LifecycleStep.IMPLEMENTATION)
    make_branch(rig.world.root, "dev/erik")
    commit_file(rig.world.root, "README.md", "dev\n", "dev work")
    _gates(rig, tmp_path, config={CF_KEY_INTEGRATION_BRANCH: "dev/erik"})

    rig.tick()

    assert _launched(rig, node).parameters[PARAM_TARGET] == "dev/erik"


def test_a_planning_entry_records_no_target(rig: DispatchRig) -> None:
    node = _step(rig, LifecycleStep.SLICE_DESIGN)

    rig.tick()

    assert PARAM_TARGET not in _launched(rig, node).parameters


# -- a failed read -------------------------------------------------------------


def test_a_failed_read_blocks_nothing_raises_a_fault_and_closes_when_it_stops(
    rig: DispatchRig, tmp_path: Path
) -> None:
    node = _step(rig)
    _gates(rig, tmp_path, mode=GateMode.FAIL)

    rig.tick()

    assert not _blocked_on_human(rig, node)
    assert rig.entries(CommandKind.SQ_RUN, node) == []
    [fault] = rig.store.open_project_escalations(PROJECT)
    assert fault.fault_kind == "checkout_read_failed"
    payload = dict(fault.payload or {})
    assert payload["command"] == "cf status --json"
    assert payload["checkout"] == str(rig.world.root)
    assert payload["reason"]

    _gates(rig, tmp_path)  # CF answers again
    rig.tick()

    assert len(rig.entries(CommandKind.SQ_RUN, node)) == 1
    assert rig.store.open_project_escalations(PROJECT) == []


# -- a reissue -----------------------------------------------------------------


def _never_started(rig: DispatchRig) -> Node:
    """A pointed step whose launch recovery resolved ``not_applied``."""
    node = _step(rig, LifecycleStep.SLICE_DESIGN)
    old = rig.store.journal_issue(
        node.id,
        kind=CommandKind.SQ_RUN,
        parameters={
            PARAM_PIPELINE: "P4",
            PARAM_PARAMS: {"slice": str(INDEX)},
            PARAM_RUN_ID: OLD_RUN_ID,
            PARAM_CHECKOUT: str(rig.world.root),
        },
    )
    rig.store.journal_resolve(
        old.id,
        outcome=JournalOutcome.NOT_APPLIED,
        result={"reason": "no run state after the grace period"},
        resolved_by=JournalResolver.RECOVERY,
    )
    rig.tick_rig.poll.answers.append(document(OLD_RUN_ID, RunOutcome.NOT_FOUND))
    return node


def test_a_reissue_is_checked_like_a_launch(rig: DispatchRig) -> None:
    node = _never_started(rig)
    _dirty(rig)

    rig.tick()

    assert _blocked_on_human(rig, node)
    assert _block_payload(rig)[PAYLOAD_FAULT_KIND] == "checkout_dirty"
    assert rig.popen.argvs == []


def test_a_clean_reissue_launches_and_records_the_check(rig: DispatchRig) -> None:
    node = _never_started(rig)

    rig.tick()

    [_, new] = rig.entries(CommandKind.SQ_RUN, node)
    assert _evidence(new)["branch"] == "main"


def test_a_blocked_launch_resolved_with_rerun_is_checked_again(
    rig: DispatchRig,
) -> None:
    node = _step(rig)
    _dirty(rig)
    rig.tick()
    assert _blocked_on_human(rig, node)
    (rig.world.root / "README.md").write_text("seed\n")  # the PM cleans up
    blocked = rig.store.blocked_state_for(node.id)
    assert blocked is not None
    resolve_block(rig.store, blocked.id, "rerun", project_id=PROJECT)

    rig.tick()  # acknowledged: the pointer is written again
    rig.tick()  # pointed: checked, and launched

    assert len(rig.entries(CommandKind.SQ_RUN, node)) == 1


# -- a resume and an observation -----------------------------------------------


def _paused_loop(rig: DispatchRig) -> tuple[Node, str]:
    node = _step(rig, LifecycleStep.SLICE_DESIGN)
    rig.tick()
    rig.end_run(
        node,
        RunOutcome.PAUSED,
        checkpoint=LOOP_CHECKPOINT,
        **write_review(rig).document,
    )
    run_id = str(rig.entries(CommandKind.SQ_RUN, node)[0].parameters[PARAM_RUN_ID])
    return node, run_id


def _resolve(rig: DispatchRig, node: Node, decision: str) -> None:
    blocked = rig.store.blocked_state_for(node.id)
    assert blocked is not None
    resolve_block(rig.store, blocked.id, decision, None, project_id=PROJECT)


def _continuation(rig: DispatchRig, node: Node) -> JournalEntry:
    [entry] = [
        e
        for e in rig.entries(CommandKind.SQ_RUN, node)
        if PARAM_CONTINUATION in e.parameters
    ]
    return entry


def test_a_resume_on_a_dirty_tree_resumes_and_names_the_dirty_paths(
    rig: DispatchRig,
) -> None:
    node, run_id = _paused_loop(rig)
    _resolve(rig, node, "retry")
    answer_poll(rig, run_id, RunOutcome.PAUSED, checkpoint=LOOP_CHECKPOINT)
    _dirty(rig)

    rig.tick()

    resumed = _continuation(rig, node)
    assert resumed.parameters[PARAM_CONTINUATION] == "retry"
    evidence = _evidence(resumed)
    assert evidence["dirty_paths"] == ["README.md"] and evidence["dirty_count"] == 1
    assert evidence["gate_status"] is None, "a resume does not read the gate"


def test_a_resume_on_the_wrong_branch_blocks(rig: DispatchRig) -> None:
    node, run_id = _paused_loop(rig)
    _resolve(rig, node, "retry")
    answer_poll(rig, run_id, RunOutcome.PAUSED, checkpoint=LOOP_CHECKPOINT)
    make_branch(rig.world.root, "feature-x")

    rig.tick()

    assert [
        e
        for e in rig.entries(CommandKind.SQ_RUN, node)
        if PARAM_CONTINUATION in e.parameters
    ] == []
    assert _block_payload(rig)[PAYLOAD_FAULT_KIND] == "checkout_branch"


def test_an_observation_is_not_checked(rig: DispatchRig) -> None:
    node, run_id = _paused_loop(rig)
    _resolve(rig, node, "handled")
    answer_poll(
        rig, run_id, RunOutcome.COMPLETED, **write_review(rig, "verdict: PASS").document
    )
    _dirty(rig)
    make_branch(rig.world.root, "feature-x")

    rig.tick()

    assert _continuation(rig, node).parameters[PARAM_CONTINUATION] == "observe"
    assert rig.store.messages(PROJECT, channel=Channel.ESCALATION) == []


def test_a_pointer_write_is_not_checked(rig: DispatchRig) -> None:
    _dirty(rig)
    make_branch(rig.world.root, "feature-x")

    node = rig.step("pointer-only", INDEX, LifecycleStep.SLICE_DESIGN)
    rig.tick()

    assert rig.entries(CommandKind.CF_WRITE, node), "the pointer write goes ahead"
    assert not _blocked_on_human(rig, node)
