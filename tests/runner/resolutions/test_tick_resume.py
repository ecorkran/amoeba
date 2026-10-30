"""A resolution carried through the tick: acknowledged, resumed, confirmed, routed."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from amoeba.process import RunCheckpoint, RunOutcome, RunOutcomeDocument
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.faults import ResumeFailure
from amoeba.runner.lifecycle.steps import Executor
from amoeba.runner.resolutions.classify import classify
from amoeba.runner.resolutions.planner import ContinuationPlanner
from amoeba.runner.resolutions.vocabulary import Situation
from amoeba.store import (
    PARAM_CONTINUATION,
    PARAM_RUN_ID,
    BlockedKind,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    Node,
    NodeStatus,
    Store,
)
from runner.dispatch.tick_rig import DispatchRig
from runner.gate_rig import clear_gates
from runner.observe_support import GRACE, Child
from runner.resolutions.resolution_support import (
    PAUSED_AT,
    block_and_resolve,
    finished_run,
    paused_document,
    resolve_block,
)
from runner.resolutions.rig_support import (
    INDEX,
    LOOP_CHECKPOINT,
    answer_poll,
    write_review,
)

STEP_INTERVAL = 20.0


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    built = DispatchRig(tmp_path, store)
    built.tick_rig.planners = (DispatchPlanner(), ContinuationPlanner())
    yield built


def _paused_step(rig: DispatchRig, decision: str, instructions: str | None) -> Node:
    """A step with a paused, routed run in the world's checkout, then resolved."""
    node = rig.step("resumable", 150)
    finished_run(
        rig.store,
        node,
        RunOutcome.PAUSED,
        document=paused_document("placeholder"),
        checkout=str(rig.world.root),
    )
    block_and_resolve(rig.store, node, decision, instructions)
    return node


def _run_id(rig: DispatchRig, node: Node) -> str:
    [first, *_] = rig.entries(CommandKind.SQ_RUN, node)
    return str(first.parameters[PARAM_RUN_ID])


def _poll(rig: DispatchRig, node: Node, outcome: RunOutcome, offset: int = 0) -> None:
    checkpoint = RunCheckpoint(paused_at=PAUSED_AT + timedelta(minutes=offset))
    rig.tick_rig.poll.answers.append(
        RunOutcomeDocument(
            run_id=_run_id(rig, node),
            outcome=outcome,
            status=outcome.value,
            checkpoint=checkpoint if outcome is RunOutcome.PAUSED else None,
        )
    )


def _continuation(rig: DispatchRig, node: Node) -> JournalEntry:
    [entry] = [
        e
        for e in rig.entries(CommandKind.SQ_RUN, node)
        if PARAM_CONTINUATION in e.parameters
    ]
    return entry


def test_a_retry_resumes_then_completes_and_is_ingested(
    rig: DispatchRig,
) -> None:
    node = _paused_step(rig, "retry", "narrow it")
    _poll(rig, node, RunOutcome.PAUSED)  # the pre-poll: still at the decided pause

    rig.tick()

    entry = _continuation(rig, node)
    assert rig.popen.argvs[-1][2:4] == ["--resume", _run_id(rig, node)]
    assert not entry.is_resolved and entry.parameters[PARAM_CONTINUATION] == "retry"

    _poll(rig, node, RunOutcome.COMPLETED)
    rig.tick_rig.clock.seconds += STEP_INTERVAL
    rig.tick()

    done = rig.store.journal_entry(entry.id)
    assert done is not None and done.outcome is JournalOutcome.COMPLETED
    stored = rig.store.get_node(node.id)
    assert stored is not None and stored.status is NodeStatus.DONE


def test_a_new_pause_after_the_retry_is_recognized_and_ingested(
    rig: DispatchRig,
) -> None:
    node = _paused_step(rig, "retry", None)
    _poll(rig, node, RunOutcome.PAUSED)
    rig.tick()
    entry = _continuation(rig, node)

    _poll(rig, node, RunOutcome.PAUSED, offset=45)
    rig.tick_rig.clock.seconds += STEP_INTERVAL
    rig.tick()

    ended = rig.store.journal_entry(entry.id)
    assert ended is not None and ended.is_resolved
    assert ended.result is not None and ended.result["outcome"] == "paused"
    stored = rig.store.get_node(node.id)
    assert stored is not None and stored.status is not NodeStatus.DONE


def test_handled_on_a_run_that_moved_on_is_observed_and_ingested(
    rig: DispatchRig,
) -> None:
    node = _paused_step(rig, "handled", None)
    _poll(rig, node, RunOutcome.COMPLETED)  # the PM finished it by hand

    rig.tick()

    entry = _continuation(rig, node)
    assert entry.parameters[PARAM_CONTINUATION] == "observe"
    assert rig.popen.argvs == [], "nothing is launched for handled"

    _poll(rig, node, RunOutcome.COMPLETED)
    rig.tick_rig.clock.seconds += STEP_INTERVAL
    rig.tick()

    done = rig.store.journal_entry(entry.id)
    assert done is not None and done.outcome is JournalOutcome.COMPLETED
    stored = rig.store.get_node(node.id)
    assert stored is not None and stored.status is NodeStatus.DONE


def test_a_resolution_is_acknowledged_before_the_resume_in_the_same_tick(
    rig: DispatchRig,
) -> None:
    node = _paused_step(rig, "retry", None)
    _poll(rig, node, RunOutcome.PAUSED)

    rig.tick()

    assert rig.store.pending_resolutions("demo") == []
    assert len(rig.popen.argvs) == 1


def _loop_paused_step(rig: DispatchRig) -> tuple[Node, str]:
    """A step whose run paused at a loop with a CONCERNS review, ingested."""
    slice_node, step = rig.slice_and_step("failed-resume", INDEX)
    clear_gates(rig, slice_node)
    rig.tick()
    rig.tick()
    rig.end_run(
        step,
        RunOutcome.PAUSED,
        checkpoint=LOOP_CHECKPOINT,
        **write_review(rig).document,
    )
    run_id = str(rig.entries(CommandKind.SQ_RUN, step)[0].parameters["run_id"])
    return step, run_id


def _issued_long_ago(rig: DispatchRig, entry: JournalEntry, seconds: float) -> None:
    """Back-date the entry on the rig's clock; the store stamps real time."""
    if not seconds:
        return
    issued = rig.tick_rig.clock.wall() - timedelta(seconds=seconds)
    with sqlite3.connect(rig.store.path) as connection:
        connection.execute(
            "UPDATE command_journal SET issued_at = ? WHERE id = ?",
            (issued.isoformat(), entry.id),
        )


@pytest.mark.parametrize(
    ("exit_code", "seconds", "failure"),
    [
        (2, 0.0, ResumeFailure.REFUSED),
        (1, 0.0, ResumeFailure.EXITED_BEFORE_CLAIM),
        (None, GRACE + 1, ResumeFailure.NO_CLAIM_WITHIN_GRACE),
    ],
)
def test_a_failed_resume_escalates_once_and_offers_the_pause_decisions_again(
    rig: DispatchRig,
    exit_code: int | None,
    seconds: float,
    failure: ResumeFailure,
) -> None:
    step, run_id = _loop_paused_step(rig)
    blocked = rig.store.blocked_state_for(step.id)
    assert blocked is not None
    resolve_block(rig.store, blocked.id, "retry", None, project_id="demo")
    answer_poll(rig, run_id, RunOutcome.PAUSED, checkpoint=LOOP_CHECKPOINT)
    rig.tick()
    entry = _continuation(rig, step)
    rig.tick_rig.tracker.track(entry.id, Child(exit_code))
    answer_poll(rig, run_id, RunOutcome.PAUSED, checkpoint=LOOP_CHECKPOINT)
    if exit_code is not None:
        # The look taken again before an exited child's resume is called failed.
        answer_poll(rig, run_id, RunOutcome.PAUSED, checkpoint=LOOP_CHECKPOINT)
    _issued_long_ago(rig, entry, seconds)
    rig.tick_rig.clock.seconds += STEP_INTERVAL

    rig.tick()

    failed = _continuation(rig, step)
    assert failed.result is not None
    assert failed.result["resume_failure"] == failure.value
    blocked = rig.store.blocked_state_for(step.id)
    assert blocked is not None and blocked.kind is BlockedKind.HUMAN
    entries = rig.store.journal_entries("demo", node_id=step.id)
    assert classify(Executor.PIPELINE, entries) is Situation.PAUSED_RUN
