"""D7 at tick level: a PM accept that CF's gate still fails is recorded, once (#15)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cf_stub_gates import STATUS_POINTER_ENV

from amoeba.inspection.checks import check_rows
from amoeba.inspection.listing import NODE_OPTION, ListingRequest
from amoeba.process import RunOutcome
from amoeba.runner.dispatch.params import PARAM_DISPATCH_CHECK
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.faults import PAYLOAD_FAULT_KIND
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.resolutions.planner import ContinuationPlanner
from amoeba.store import (
    BlockedKind,
    Channel,
    CheckOutcome,
    CommandKind,
    Node,
    NodeStatus,
    Store,
)
from runner.dispatch.tick_rig import DispatchRig
from runner.gate_rig import STATUS_FIXTURES, config_knobs
from runner.resolutions.resolution_support import resolve_block
from runner.resolutions.rig_support import INDEX, tasks_step, write_review

PROJECT = "demo"
DISAGREEMENT = "cf_gate_accept_disagreement"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    built = DispatchRig(tmp_path, store)
    built.tick_rig.planners = (DispatchPlanner(), ContinuationPlanner())
    # CF's slice gate has failed the whole time: its review artifact says FAIL.
    built.tick_rig.gate_run = built.world.run(
        {
            STATUS_POINTER_ENV: str(STATUS_FIXTURES / "review_failed_slice.json"),
            **config_knobs(tmp_path, {}),
        }
    )
    yield built


def _accepted_design(rig: DispatchRig) -> tuple[Node, Node]:
    """A slice design whose stated PASS CF's gate fails, escalated, then accepted.

    Returns the slice node and its ``tasks`` step, ready to dispatch.
    """
    slice_node, design = rig.slice_and_step("gated", INDEX)
    rig.tick()
    rig.tick()
    rig.end_run(
        design, RunOutcome.COMPLETED, **write_review(rig, "verdict: PASS").document
    )
    state = rig.store.blocked_state_for(design.id)
    assert state is not None and state.kind is BlockedKind.HUMAN, (
        "CF's gate escalates it"
    )
    tasks = tasks_step(rig, slice_node)
    resolve_block(rig.store, state.id, "accept", project_id=PROJECT)
    rig.tick()  # accepted: the design is done, and the tasks pointer is written
    assert rig.status(design) is NodeStatus.DONE
    return slice_node, tasks


def _disagreements(rig: DispatchRig, slice_node: Node) -> list[tuple[str, str]]:
    return [
        (check.id, check.outcome.value)
        for check in rig.store.checks(PROJECT, node_id=slice_node.id)
        if check.name == DISAGREEMENT
    ]


def test_after_a_pm_accept_the_failing_gate_is_recorded_and_tasks_launches(
    rig: DispatchRig,
) -> None:
    slice_node, tasks = _accepted_design(rig)

    rig.tick()

    [(check_id, outcome)] = _disagreements(rig, slice_node)
    assert outcome == CheckOutcome.FAILED.value
    [run] = rig.entries(CommandKind.SQ_RUN, tasks)
    evidence = run.parameters[PARAM_DISPATCH_CHECK]
    assert isinstance(evidence, dict) and evidence["disagreement_check"] == check_id
    assert evidence["gate_status"] == "review-failed"
    record = rig.store.check(check_id)
    assert record is not None
    assert record.examined_count == 1
    examined = dict(record.examined or {})
    assert examined["step"] == "slice_design"
    assert (
        examined["cf_status"] == "review-failed" and examined["review_type"] == "slice"
    )
    assert "FAIL" in str(examined["rationale"])
    assert examined["accepted_by"] and examined["verdict_ids"]


def test_accept_disagreement_recorded_once(rig: DispatchRig) -> None:
    slice_node, tasks = _accepted_design(rig)
    rig.tick()  # the tasks launch
    rig.end_run(
        tasks, RunOutcome.COMPLETED, **write_review(rig, "verdict: PASS").document
    )
    state = rig.store.blocked_state_for(tasks.id)
    assert state is not None, "CF is still not at the tasks gate: escalated"
    resolve_block(rig.store, state.id, "rerun", project_id=PROJECT)

    rig.tick()  # acknowledged, pointer written
    rig.tick()  # checked again, launched again

    assert len(rig.entries(CommandKind.SQ_RUN, tasks)) == 2
    assert len(_disagreements(rig, slice_node)) == 1


def test_without_an_accept_the_same_gate_blocks_cf_gate_blocks(
    rig: DispatchRig,
) -> None:
    _, tasks = rig.slice_and_step("unaccepted", INDEX, LifecycleStep.TASKS)
    rig.tick()  # the pointer write

    rig.tick()

    state = rig.store.blocked_state_for(tasks.id)
    assert state is not None and state.kind is BlockedKind.HUMAN
    [message] = rig.store.messages(PROJECT, channel=Channel.ESCALATION)
    assert dict(message.payload or {})[PAYLOAD_FAULT_KIND] == "cf_gate_blocks"
    assert rig.entries(CommandKind.SQ_RUN, tasks) == []


def test_inspect_checks_shows_the_disagreement_on_the_slice(rig: DispatchRig) -> None:
    slice_node, _ = _accepted_design(rig)
    rig.tick()

    rows = check_rows(
        rig.store, ListingRequest(PROJECT, {NODE_OPTION.name: slice_node.id}, False)
    )

    [row] = [r for r in rows if r["name"] == DISAGREEMENT]
    assert row["standing"] == "failed" and row["upstream"] == "amoeba"
    assert row["source"] == "command_output"
