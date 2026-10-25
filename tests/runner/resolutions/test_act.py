"""The continuation act's pre-poll, wait, run-missing and observe branches (D4)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from amoeba.process import (
    PollFailure,
    RunCheckpoint,
    RunOutcome,
    RunOutcomeDocument,
    RunPoll,
)
from amoeba.runner.decide import ObserveRun, ResumeRun
from amoeba.runner.faults import FaultKind, TickFaults
from amoeba.runner.finish import RESULT_RESUME_FAILURE
from amoeba.runner.resolutions.act import Acted, ContinuationActs
from amoeba.runner.resolutions.vocabulary import (
    PARAM_RESUME_SKIPPED,
    RESUME_SKIPPED_RUN_NOT_AT_PAUSE,
    Continuation,
)
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_CONTINUATION,
    PARAM_CONTINUES,
    PARAM_RESOLUTION,
    PARAM_RUN_ID,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    NodeStatus,
    Store,
)
from runner.dispatch.pointer_support import budget_allowing, generous_budget
from runner.observe_support import ScriptedPoll
from runner.resolutions.resolution_support import (
    PAUSED_AT,
    design_step,
    finished_run,
    paused_document,
)
from runner.tick_support import PROJECT

CHECKOUT = "/work/a"


class Rig:
    """A paused step, its resume action, and the act under test."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self.node = design_step(store)
        self.entry: JournalEntry = finished_run(
            store,
            self.node,
            RunOutcome.PAUSED,
            document=paused_document("placeholder"),
            checkout=CHECKOUT,
        )
        self.run_id = str(self.entry.parameters[PARAM_RUN_ID])
        self.poll = ScriptedPoll()
        self.acts = ContinuationActs(
            store=store, poll_run=self.poll, version_label="sq-label"
        )
        self.faults = TickFaults()

    def resume(self, decision: Continuation = Continuation.RETRY) -> ResumeRun:
        return ResumeRun(
            self.node.id, self.run_id, decision, self.entry.id, "b-1", Path(CHECKOUT)
        )

    def observe(self) -> ObserveRun:
        return ObserveRun(
            self.node.id, self.run_id, self.entry.id, "b-1", Path(CHECKOUT)
        )

    def answer(self, *polls: RunPoll) -> None:
        self.poll.answers.extend(polls)

    def entries(self) -> list[JournalEntry]:
        return self.store.journal_entries(PROJECT, node_id=self.node.id)

    def paused(self, offset: int = 0) -> RunOutcomeDocument:
        return RunOutcomeDocument(
            run_id=self.run_id,
            outcome=RunOutcome.PAUSED,
            checkpoint=RunCheckpoint(paused_at=PAUSED_AT + timedelta(minutes=offset)),
        )


@pytest.fixture
def rig(store: Store) -> Rig:
    return Rig(store)


def test_a_spent_budget_polls_and_writes_nothing(rig: Rig) -> None:
    result = rig.acts.act(rig.resume(), budget_allowing(0), rig.faults)

    assert result is Acted.CUT_OFF
    assert rig.poll.asked == [] and len(rig.entries()) == 1


def test_a_failed_pre_poll_writes_nothing_and_records_a_fault(rig: Rig) -> None:
    rig.answer(PollFailure("sq timed out"))

    result = rig.acts.act(rig.resume(), generous_budget(), rig.faults)

    assert result is Acted.WAITED
    assert len(rig.entries()) == 1
    [fault] = list(rig.faults)
    assert fault.kind is FaultKind.RUN_OBSERVATION_FAILED
    assert fault.node_id == rig.node.id and "sq timed out" in fault.detail


def test_missing_run_launches_nothing(rig: Rig) -> None:
    rig.answer(RunOutcomeDocument(run_id=rig.run_id, outcome=RunOutcome.NOT_FOUND))

    result = rig.acts.act(rig.resume(), generous_budget(), rig.faults)

    assert result is Acted.WROTE
    continuation = rig.entries()[-1]
    assert continuation.parameters[PARAM_CONTINUATION] == "retry"
    assert continuation.outcome is JournalOutcome.FAILED
    assert continuation.result is not None
    assert continuation.result[RESULT_RESUME_FAILURE] == "run_missing"
    node = rig.store.get_node(rig.node.id)
    assert node is not None and node.status is NodeStatus.BLOCKED_ON_HUMAN


def test_run_moved_by_hand_is_observed(rig: Rig) -> None:
    rig.answer(rig.paused(offset=30))

    result = rig.acts.act(rig.resume(), generous_budget(), rig.faults)

    assert result is Acted.WROTE
    observation = rig.entries()[-1]
    assert not observation.is_resolved
    assert observation.parameters[PARAM_CONTINUATION] == "observe"
    assert observation.parameters[PARAM_RESUME_SKIPPED] == (
        RESUME_SKIPPED_RUN_NOT_AT_PAUSE
    )


def test_handled_journals_an_observation_and_launches_nothing(rig: Rig) -> None:
    rig.answer(rig.paused())

    result = rig.acts.act(rig.observe(), generous_budget(), rig.faults)

    assert result is Acted.WROTE
    observation = rig.entries()[-1]
    assert observation.kind is CommandKind.SQ_RUN and not observation.is_resolved
    assert PARAM_RESUME_SKIPPED not in observation.parameters
    assert observation.parameters[PARAM_CONTINUATION] == "observe"


def test_the_continuation_carries_the_continued_run_and_names_both_ends(
    rig: Rig,
) -> None:
    rig.answer(rig.paused())

    rig.acts.act(rig.observe(), generous_budget(), rig.faults)

    observation = rig.entries()[-1]
    assert observation.parameters[PARAM_RUN_ID] == rig.run_id
    assert observation.parameters[PARAM_CHECKOUT] == CHECKOUT
    assert observation.parameters[PARAM_CONTINUES] == rig.entry.id
    assert observation.parameters[PARAM_RESOLUTION] == "b-1"
    assert observation.parameters["pipeline"] == rig.entry.parameters["pipeline"]


def test_the_second_budget_check_cuts_off_before_anything_is_journaled(
    rig: Rig,
) -> None:
    rig.answer(rig.paused(offset=30))

    result = rig.acts.act(rig.resume(), budget_allowing(1), rig.faults)

    assert result is Acted.CUT_OFF
    assert len(rig.entries()) == 1


def test_a_continued_entry_that_is_gone_is_a_defect(rig: Rig) -> None:
    action = ResumeRun(
        rig.node.id, rig.run_id, Continuation.RETRY, "no-such", "b-1", Path(CHECKOUT)
    )

    with pytest.raises(ValueError, match="does not exist"):
        rig.acts.act(action, generous_budget(), rig.faults)
