"""A resolution carried through the tick: acknowledged, resumed, confirmed, routed."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from amoeba.process import RunCheckpoint, RunOutcome, RunOutcomeDocument
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.resolutions.planner import ContinuationPlanner
from amoeba.store import (
    PARAM_CONTINUATION,
    PARAM_RUN_ID,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    Node,
    NodeStatus,
    Store,
)
from runner.dispatch.tick_rig import DispatchRig
from runner.resolutions.resolution_support import (
    PAUSED_AT,
    block_and_resolve,
    finished_run,
    paused_document,
)
from runner.routing.table_support import ADVANCE_COMPLETED, small_table

STEP_INTERVAL = 20.0


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    built = DispatchRig(tmp_path, store)
    built.tick_rig.planners = (DispatchPlanner(), ContinuationPlanner())
    built.tick_rig.routing_table = small_table(ADVANCE_COMPLETED)
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


def _decision_route(rig: DispatchRig, entry: JournalEntry) -> str:
    decision = rig.store.routing_decision_for_entry(entry.id)
    assert decision is not None
    return decision.route.value


def test_a_retry_resumes_then_completes_and_is_ingested_and_routed(
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
    assert _decision_route(rig, done) == "advance"
    stored = rig.store.get_node(node.id)
    assert stored is not None and stored.status is NodeStatus.DONE


def test_a_new_pause_after_the_retry_is_recognized_ingested_and_escalated(
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
    assert _decision_route(rig, ended) == "escalate"
    stored = rig.store.get_node(node.id)
    assert stored is not None and stored.status is not NodeStatus.DONE


def test_handled_on_a_run_that_moved_on_is_observed_ingested_and_routed(
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
    assert _decision_route(rig, done) == "advance"


def test_a_resolution_is_acknowledged_before_the_resume_in_the_same_tick(
    rig: DispatchRig,
) -> None:
    node = _paused_step(rig, "retry", None)
    _poll(rig, node, RunOutcome.PAUSED)

    rig.tick()

    assert rig.store.pending_resolutions("demo") == []
    assert len(rig.popen.argvs) == 1
