"""Recording a failed resume: the block, the result, and what the journal then says."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from amoeba.process import RunCheckpoint, RunOutcome, RunOutcomeDocument
from amoeba.runner.dispatch.hold import checkout_holders
from amoeba.runner.faults import ResumeFailure
from amoeba.runner.finish import (
    PAYLOAD_EXIT_CODE,
    PAYLOAD_STDERR_TAIL,
    RESULT_RESUME_FAILURE,
    record_unstarted,
)
from amoeba.runner.ingest.record import RESULT_OUTCOME, RESULT_OUTCOME_DOCUMENT
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.runner.lifecycle.steps import Executor
from amoeba.runner.observed import ResumeFailed
from amoeba.runner.resolutions.classify import classify
from amoeba.runner.resolutions.vocabulary import REASON_RESUME_FAILED, Situation
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_RUN_ID,
    Channel,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    Node,
    NodeKind,
    Store,
)

PROJECT = "demo"
RUN_ID = "run-1"
CHECKOUT = Path("/work/a")
PAUSED_AT = datetime(2026, 10, 25, 9, 30, tzinfo=UTC)


@pytest.fixture
def node(store: Store) -> Node:
    return store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")


@pytest.fixture
def entry(store: Store, node: Node) -> JournalEntry:
    return store.journal_issue(
        node.id,
        kind=CommandKind.SQ_RUN,
        parameters={
            PARAM_PIPELINE: "P5",
            PARAM_PARAMS: {},
            PARAM_RUN_ID: RUN_ID,
            PARAM_CHECKOUT: str(CHECKOUT),
        },
    )


def _paused() -> RunOutcomeDocument:
    return RunOutcomeDocument(
        run_id=RUN_ID,
        outcome=RunOutcome.PAUSED,
        checkpoint=RunCheckpoint(kind="loop_exhausted", paused_at=PAUSED_AT),
    )


def _resolved(store: Store, entry: JournalEntry) -> JournalEntry:
    found = store.journal_entry(entry.id)
    assert found is not None
    return found


def _routed(entry: JournalEntry) -> JournalEntry:
    """The entry after a routing decision cleared its flag."""
    return replace(entry, awaits_routing=False)


def _fail(
    store: Store,
    entry: JournalEntry,
    failure: ResumeFailure,
    exit_code: int | None = None,
) -> JournalEntry:
    document = RunOutcomeDocument(run_id=RUN_ID, outcome=RunOutcome.NOT_FOUND)
    last = document if failure is ResumeFailure.RUN_MISSING else _paused()
    record_unstarted(store, entry, ResumeFailed(failure, exit_code, "boom", last))
    return _resolved(store, entry)


def test_a_refused_resume_keeps_the_pause_and_blocks_with_the_failure(
    store: Store, node: Node, entry: JournalEntry
) -> None:
    done = _fail(store, entry, ResumeFailure.REFUSED, 2)

    assert done.outcome is JournalOutcome.FAILED and done.awaits_routing is True
    assert done.result is not None
    assert done.result[RESULT_OUTCOME] == "paused"
    assert done.result[RESULT_RESUME_FAILURE] == "refused"
    document = done.result[RESULT_OUTCOME_DOCUMENT]
    assert isinstance(document, dict) and document["outcome"] == "paused"
    [message] = store.messages(PROJECT, channel=Channel.ESCALATION)
    assert message.payload == {
        "reason": REASON_RESUME_FAILED,
        RESULT_RESUME_FAILURE: "refused",
        "run_id": RUN_ID,
        PAYLOAD_EXIT_CODE: 2,
        PAYLOAD_STDERR_TAIL: "boom",
    }


def test_a_missing_run_resolves_not_found(
    store: Store, node: Node, entry: JournalEntry
) -> None:
    done = _fail(store, entry, ResumeFailure.RUN_MISSING)

    assert done.result is not None
    assert done.result[RESULT_OUTCOME] == "not_found"
    assert done.result[RESULT_RESUME_FAILURE] == "run_missing"


@pytest.mark.parametrize(
    "failure",
    [
        ResumeFailure.REFUSED,
        ResumeFailure.EXITED_BEFORE_CLAIM,
        ResumeFailure.NO_CLAIM_WITHIN_GRACE,
        ResumeFailure.SPAWN_ERROR,
    ],
)
def test_a_failed_resume_keeps_the_checkout_held_and_reads_paused_run(
    store: Store, node: Node, entry: JournalEntry, failure: ResumeFailure
) -> None:
    done = _fail(store, entry, failure)

    assert set(checkout_holders([done], set(), {})) == {CHECKOUT}
    assert classify(Executor.PIPELINE, [_routed(done)]) is Situation.PAUSED_RUN


def test_after_a_missing_run_the_hold_is_released_and_the_run_has_ended(
    store: Store, node: Node, entry: JournalEntry
) -> None:
    done = _fail(store, entry, ResumeFailure.RUN_MISSING)

    assert set(checkout_holders([done], set(), {})) == frozenset()
    assert classify(Executor.PIPELINE, [_routed(done)]) is Situation.ENDED_RUN


def test_the_node_is_blocked_once_even_if_recorded_again(
    store: Store, node: Node, entry: JournalEntry
) -> None:
    record_unstarted(
        store, entry, ResumeFailed(ResumeFailure.REFUSED, 2, "x", _paused())
    )
    reloaded = _resolved(store, entry)
    assert reloaded.is_resolved

    assert len([s for s in store.all_blocked_states(node.id) if not s.is_resolved]) == 1
