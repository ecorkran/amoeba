"""Automatic resume through the real tick: transient outcomes, within a bound.

Slice 132, D5. The tick, the planners and the store are the production ones; the run
is a scripted ``sq runs wait`` and a fake launch. Each failure carries a later
``updated_at`` than the last, as a real run does, so a resume is told from the old
state it left.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from amoeba.process import RunOutcomeDocument
from amoeba.runner.launch import log_paths
from amoeba.runner.resolutions.vocabulary import PARAM_RESUME_CAUSE, ResumeCause
from amoeba.runner.supervise import (
    REASON_AUTO_RESUME_EXHAUSTED,
)
from amoeba.store import (
    PARAM_RUN_ID,
    BlockedKind,
    Channel,
    CommandKind,
    JournalEntry,
    Node,
    NodeStatus,
    Store,
)
from runner.dispatch.tick_rig import DispatchRig
from runner.gate_rig import clear_gates
from runner.intent.intent_support import submit
from runner.resolutions.rig_support import INDEX

PROJECT = "demo"
FIRST_STEP = "design-0"
T0 = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    yield DispatchRig(tmp_path, store)


def _launched(rig: DispatchRig) -> Node:
    slice_node, step = rig.slice_and_step("auto-resume", INDEX)
    clear_gates(rig, slice_node)
    rig.tick()
    rig.tick()
    assert rig.run_of(step)
    return step


def _document(run_id: str, minute: int, **fields: object) -> RunOutcomeDocument:
    return RunOutcomeDocument.model_validate(
        {
            "run_id": run_id,
            "updated_at": (T0 + timedelta(minutes=minute)).isoformat(),
            **fields,
        }
    )


def _stop(
    rig: DispatchRig,
    node: Node,
    minute: int,
    *,
    resumed: bool = True,
    **fields: object,
) -> None:
    """The node's open run ends in the way ``fields`` say, and the tick sees it.

    ``resumed`` queues the pre-poll answer a resume issued in that tick reads: the
    run, still in the state it stopped in.
    """
    entry = rig.run_of(node)
    run_id = str(entry.parameters[PARAM_RUN_ID])
    rig.tick_rig.tracker.confirm(entry.id)
    log_paths(rig.tick_rig.supervisor_dir, entry.id).stderr.write_text(
        f"run_id={run_id}\n"
    )
    stopped = _document(run_id, minute, **fields)
    rig.tick_rig.poll.answers.append(stopped)
    if resumed:
        rig.tick_rig.poll.answers.append(stopped)
    rig.tick_rig.clock.seconds += 20.0
    rig.tick()


def _fail(rig: DispatchRig, node: Node, minute: int, step: str, **kw: bool) -> None:
    failure = {"kind": "stall", "step": step, "message": "no progress"}
    _stop(rig, node, minute, outcome="failed", failure=failure, **kw)


def _resumes(rig: DispatchRig, node: Node) -> list[JournalEntry]:
    return [
        e
        for e in rig.entries(CommandKind.SQ_RUN, node)
        if e.parameters.get(PARAM_RESUME_CAUSE) == ResumeCause.TRANSIENT.value
    ]


def test_two_transient_failures_then_completion_resume_twice_then_finish(
    rig: DispatchRig,
) -> None:
    step = _launched(rig)

    _fail(rig, step, 1, FIRST_STEP)
    _fail(rig, step, 2, FIRST_STEP)
    assert len(_resumes(rig, step)) == 2
    _stop(rig, step, 3, resumed=False, outcome="completed", reviews=[])

    assert len(_resumes(rig, step)) == 2
    assert rig.status(step) is NodeStatus.DONE
    assert rig.store.blocked_state_for(step.id) is None


def test_four_failures_at_one_step_block_the_fourth_as_exhausted(
    rig: DispatchRig,
) -> None:
    step = _launched(rig)

    for minute in (1, 2, 3):
        _fail(rig, step, minute, FIRST_STEP)
    assert len(_resumes(rig, step)) == 3
    _fail(rig, step, 4, FIRST_STEP, resumed=False)

    assert len(_resumes(rig, step)) == 3, "no fourth resume"
    blocked = rig.store.blocked_state_for(step.id)
    assert blocked is not None and blocked.kind is BlockedKind.HUMAN
    [message] = [
        m
        for m in rig.store.messages(PROJECT, channel=Channel.ESCALATION)
        if m.blocked_state_id == blocked.id
    ]
    payload = dict(message.payload or {})
    assert payload["reason"] == REASON_AUTO_RESUME_EXHAUSTED
    assert payload["step"] == FIRST_STEP and payload["count"] == 3


def test_three_steps_once_each_are_all_resumed(rig: DispatchRig) -> None:
    step = _launched(rig)

    _fail(rig, step, 1, "design-0")
    _fail(rig, step, 2, "tasks-0")
    _fail(rig, step, 3, "implement-6")
    _stop(rig, step, 4, resumed=False, outcome="completed", reviews=[])

    assert len(_resumes(rig, step)) == 3
    assert rig.status(step) is NodeStatus.DONE
    assert rig.store.blocked_state_for(step.id) is None


def test_a_usage_limit_pause_waits_for_its_reset_time(rig: DispatchRig) -> None:
    step = _launched(rig)
    resets_at = rig.tick_rig.clock.wall() + timedelta(minutes=10)
    pause = {
        "kind": "usage_limit",
        "step": FIRST_STEP,
        "paused_at": T0.isoformat(),
        "resets_at": resets_at.isoformat(),
    }

    _stop(rig, step, 1, resumed=False, outcome="paused", checkpoint=pause)
    assert _resumes(rig, step) == [], "not before the limit resets"
    assert rig.store.blocked_state_for(step.id) is None

    run_id = str(rig.entries(CommandKind.SQ_RUN, step)[0].parameters[PARAM_RUN_ID])
    rig.tick_rig.clock.seconds += 11 * 60
    rig.tick_rig.poll.answers.append(
        _document(run_id, 1, outcome="paused", checkpoint=pause)
    )
    rig.tick()

    assert len(_resumes(rig, step)) == 1


def test_releasing_a_hold_resumes(rig: DispatchRig) -> None:
    step = _launched(rig)
    submit(rig.store, {"intent": "pause"}, project_id=PROJECT)

    _fail(rig, step, 1, FIRST_STEP, resumed=False)
    assert _resumes(rig, step) == [], "a held project resumes nothing"

    run_id = str(rig.entries(CommandKind.SQ_RUN, step)[0].parameters[PARAM_RUN_ID])
    failure = {"kind": "stall", "step": FIRST_STEP, "message": "no progress"}
    submit(rig.store, {"intent": "resume"}, project_id=PROJECT)
    rig.tick_rig.poll.answers.append(
        _document(run_id, 1, outcome="failed", failure=failure)
    )
    rig.tick()

    assert len(_resumes(rig, step)) == 1
