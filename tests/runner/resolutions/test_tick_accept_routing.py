"""Accepted loops and failed resumes, routed by the shipped table through the tick."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from amoeba.process import RunOutcome
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.faults import ResumeFailure
from amoeba.runner.lifecycle.steps import Executor
from amoeba.runner.resolutions.classify import classify
from amoeba.runner.resolutions.planner import ContinuationPlanner
from amoeba.runner.resolutions.vocabulary import Situation
from amoeba.store import (
    PARAM_CONTINUATION,
    BlockedKind,
    CommandKind,
    JournalEntry,
    Node,
    NodeStatus,
    Route,
    RoutingDecision,
    Store,
)
from runner.dispatch.tick_rig import DispatchRig
from runner.observe_support import GRACE, Child
from runner.resolutions.resolution_support import resolve_block
from runner.resolutions.rig_support import (
    INDEX,
    LOOP_CHECKPOINT,
    STATED_CONCERNS,
    answer_poll,
    write_review,
)
from runner.routing.table_support import shipped_table

SLICE = "accepted"
STEP_SECONDS = 20.0


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    built = DispatchRig(tmp_path, store)
    built.tick_rig.planners = (DispatchPlanner(), ContinuationPlanner())
    built.tick_rig.routing_table = shipped_table()
    yield built


def _paused_loop(rig: DispatchRig) -> tuple[Node, str]:
    """A step whose run paused at a loop with a CONCERNS review, ingested and routed."""
    _, step = rig.slice_and_step(SLICE, INDEX)
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


def _resolve(rig: DispatchRig, step: Node, decision: str) -> None:
    blocked = rig.store.blocked_state_for(step.id)
    assert blocked is not None
    resolve_block(rig.store, blocked.id, decision, None, project_id="demo")


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


def _continuation(rig: DispatchRig, step: Node) -> JournalEntry:
    [entry] = [
        e
        for e in rig.entries(CommandKind.SQ_RUN, step)
        if PARAM_CONTINUATION in e.parameters
    ]
    return rig.store.journal_entry(entry.id) or entry


def _decision_for(rig: DispatchRig, entry: JournalEntry) -> RoutingDecision:
    [decision] = [
        d
        for d in rig.store.routing_decisions(entry.node_id)
        if d.journal_entry_id == entry.id
    ]
    return decision


def _accept_and_finish(
    rig: DispatchRig, verdict: str = STATED_CONCERNS
) -> tuple[Node, JournalEntry]:
    step, run_id = _paused_loop(rig)
    _resolve(rig, step, "accept")
    answer_poll(rig, run_id, RunOutcome.PAUSED, checkpoint=LOOP_CHECKPOINT)
    rig.tick()  # acknowledged, then resumed
    review = write_review(rig, verdict)
    answer_poll(rig, run_id, RunOutcome.COMPLETED, **review.document)
    rig.tick_rig.clock.seconds += STEP_SECONDS
    rig.tick()  # confirmed, ingested and routed
    return step, _continuation(rig, step)


def test_an_accepted_loop_ending_on_the_accepted_review_advances(
    rig: DispatchRig,
) -> None:
    step, entry = _accept_and_finish(rig)

    decision = _decision_for(rig, entry)

    assert (decision.rule_id, decision.route) == (
        "advance-on-accepted-review",
        Route.ADVANCE,
    )
    assert decision.inputs["review_accepted"] == "true"
    assert rig.status(step) is NodeStatus.DONE


def test_an_accepted_loop_that_wrote_a_newer_review_routes_on_that_review(
    rig: DispatchRig,
) -> None:
    _, entry = _accept_and_finish(rig, verdict="verdict: PASS")

    decision = _decision_for(rig, entry)

    assert decision.rule_id == "advance-on-stated-pass"
    assert decision.inputs["review_accepted"] == "false"


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
    step, run_id = _paused_loop(rig)
    _resolve(rig, step, "retry")
    answer_poll(rig, run_id, RunOutcome.PAUSED, checkpoint=LOOP_CHECKPOINT)
    rig.tick()
    entry = _continuation(rig, step)
    rig.tick_rig.tracker.track(entry.id, Child(exit_code))
    answer_poll(rig, run_id, RunOutcome.PAUSED, checkpoint=LOOP_CHECKPOINT)
    _issued_long_ago(rig, entry, seconds)
    rig.tick_rig.clock.seconds += STEP_SECONDS

    rig.tick()

    failed = _continuation(rig, step)
    assert failed.result is not None
    assert failed.result["resume_failure"] == failure.value
    decision = _decision_for(rig, failed)
    assert (decision.route, decision.inputs["outcome"]) == (
        Route.ESCALATE,
        "resume_failed",
    )
    blocked = rig.store.blocked_state_for(step.id)
    assert blocked is not None and blocked.kind is BlockedKind.HUMAN
    entries = rig.store.journal_entries("demo", node_id=step.id)
    assert classify(Executor.PIPELINE, entries) is Situation.PAUSED_RUN
