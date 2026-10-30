"""Each resolution decision through the real tick, for those no earlier task proves.

Retry, accept of a pause and handled are proven in test_tick_resume.py. Here: accept
of an escalated completed outcome, rerun, stop, and a resolution on a held step.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.process import RunOutcome
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.launch import PARAM_REISSUE_OF
from amoeba.runner.resolutions.planner import ContinuationPlanner
from amoeba.runner.resolutions.vocabulary import REASON_STOPPED
from amoeba.store import (
    BlockedKind,
    Channel,
    CommandKind,
    JournalOutcome,
    JournalResolver,
    Node,
    NodeStatus,
    ResolutionOutcome,
    Store,
)
from runner.dispatch.tick_rig import DispatchRig
from runner.intent.intent_support import submit
from runner.resolutions.resolution_support import resolve_block
from runner.resolutions.rig_support import (
    LOOP_CHECKPOINT,
    PROJECT,
    answer_poll,
    launched_step,
    write_review,
)


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    built = DispatchRig(tmp_path, store)
    built.tick_rig.planners = (DispatchPlanner(), ContinuationPlanner())
    yield built


def _resolve(rig: DispatchRig, step: Node, decision: str) -> str:
    blocked = rig.store.blocked_state_for(step.id)
    assert blocked is not None
    return resolve_block(rig.store, blocked.id, decision, project_id=PROJECT)


def _blocked_failure(rig: DispatchRig, name: str) -> tuple[Node, Node]:
    """A step whose run failed in a way only a person can answer: blocked on a human."""
    slice_node, step = launched_step(rig, name)
    rig.end_run(
        step,
        RunOutcome.FAILED,
        failure={"kind": "cost_cap", "step": "implement-6", "message": "cap hit"},
        reviews=[],
    )
    assert rig.status(step) is NodeStatus.BLOCKED_ON_HUMAN
    return slice_node, step


def test_rerun_after_a_not_applied_launch_is_a_fresh_run_not_a_reissue(
    rig: DispatchRig,
) -> None:
    _, step = launched_step(rig, "rerun-not-applied")
    [first] = rig.entries(CommandKind.SQ_RUN, step)
    rig.store.journal_resolve(
        first.id,
        outcome=JournalOutcome.NOT_APPLIED,
        resolved_by=JournalResolver.RECOVERY,
    )
    rig.store.block(step.id, kind=BlockedKind.HUMAN, context="never started")
    _resolve(rig, step, "rerun")

    rig.tick()
    rig.tick()

    second = rig.entries(CommandKind.SQ_RUN, step)[-1]
    assert second.id != first.id
    assert PARAM_REISSUE_OF not in second.parameters
    assert second.parameters["run_id"] != first.parameters["run_id"]


def test_stop_blocks_the_node_with_reason_stopped_and_issues_nothing(
    rig: DispatchRig,
) -> None:
    _, step = _blocked_failure(rig, "stopped")
    argvs_before = len(rig.popen.argvs)
    entries_before = len(rig.store.journal_entries(PROJECT, node_id=step.id))
    blocked_id = _resolve(rig, step, "stop")

    rig.tick()
    rig.tick()

    assert rig.status(step) is NodeStatus.BLOCKED_ON_HUMAN
    stop = rig.store.blocked_state_for(step.id)
    assert stop is not None and stop.id != blocked_id
    assert stop.context == "stopped by pm"
    [message] = [
        m
        for m in rig.store.messages(PROJECT, channel=Channel.ESCALATION)
        if m.blocked_state_id == stop.id
    ]
    assert message.payload is not None and message.payload["reason"] == REASON_STOPPED
    assert len(rig.popen.argvs) == argvs_before
    assert len(rig.store.journal_entries(PROJECT, node_id=step.id)) == entries_before


def test_a_held_steps_resolution_is_acknowledged_and_its_resume_waits(
    rig: DispatchRig,
) -> None:
    _, step = launched_step(rig, "held")
    rig.end_run(
        step,
        RunOutcome.PAUSED,
        checkpoint=LOOP_CHECKPOINT,
        **write_review(rig).document,
    )
    run_id = str(rig.entries(CommandKind.SQ_RUN, step)[0].parameters["run_id"])
    submit(rig.store, {"intent": "pause"}, project_id=PROJECT)
    blocked_id = _resolve(rig, step, "retry")
    argvs_before = len(rig.popen.argvs)

    rig.tick()

    state = rig.store.blocked_state(blocked_id)
    assert state is not None and state.runner_outcome is ResolutionOutcome.APPLIED
    assert len(rig.popen.argvs) == argvs_before, "held: nothing resumed"

    submit(rig.store, {"intent": "resume"}, project_id=PROJECT)
    answer_poll(rig, run_id, RunOutcome.PAUSED, checkpoint=LOOP_CHECKPOINT)
    rig.tick()

    assert len(rig.popen.argvs) == argvs_before + 1
    assert rig.popen.argvs[-1][2:4] == ["--resume", run_id]
