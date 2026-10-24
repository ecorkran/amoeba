"""Ingestion end to end through the real tick: three outcomes, then routing.

The run's outcome document and its review files come from the stub ``sq`` scripts
(real captured shapes); the launch is a fake that starts nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sq_stub_scripts import RunScript, missing_file_review, single_review

from amoeba.process import RunOutcome
from amoeba.runner.faults import PAYLOAD_FAULT_KIND, FaultKind
from amoeba.runner.ingest.record import (
    RESULT_OUTCOME_DOCUMENT,
    RESULT_REVIEW_FAULT,
    RESULT_VERDICT_IDS,
)
from amoeba.store import (
    BlockedKind,
    Channel,
    CommandKind,
    JournalOutcome,
    Node,
    NodeStatus,
    Store,
)
from runner.dispatch.tick_rig import DispatchRig
from runner.ingest.routing_support import route_outcome

PROJECT = "demo"
SLICE = "ingest-slice"
INDEX = 125
#: What the pointer write renames the slice to: CF's own slug for index 125.
CF_SLUG = "run-dispatch-and-outcome-ingestion"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    yield DispatchRig(tmp_path, store)


def _launched(rig: DispatchRig) -> Node:
    node = rig.step(SLICE, INDEX)
    rig.tick()
    rig.tick()
    assert rig.run_of(node)
    return node


def _write(rig: DispatchRig, script: RunScript) -> None:
    for relative, text in script.files.items():
        target = rig.world.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def _open_blocks(rig: DispatchRig, node: Node) -> list[BlockedKind]:
    states = rig.store.all_blocked_states(node.id)
    return [state.kind for state in states if not state.is_resolved]


def _unrouted_ids(rig: DispatchRig) -> list[str]:
    return [entry.id for entry in rig.store.unrouted_outcomes(PROJECT)]


def _no_new_work(rig: DispatchRig, node: Node) -> None:
    pointers = len(rig.entries(CommandKind.CF_WRITE, node))
    runs = len(rig.entries(CommandKind.SQ_RUN, node))
    launches = len(rig.popen.argvs)
    rig.tick()
    rig.tick()
    assert len(rig.entries(CommandKind.CF_WRITE, node)) == pointers
    assert len(rig.entries(CommandKind.SQ_RUN, node)) == runs
    assert len(rig.popen.argvs) == launches


def test_a_paused_run_blocks_on_the_checkpoint_and_keeps_it_in_the_result(
    rig: DispatchRig,
) -> None:
    node = _launched(rig)
    review = single_review(CF_SLUG)
    _write(rig, review)
    entry = rig.run_of(node)

    rig.end_run(
        node,
        RunOutcome.PAUSED,
        checkpoint={"kind": "awaits_human", "step": "branch-10"},
        **review.document,
    )

    assert _open_blocks(rig, node) == [BlockedKind.SQ_CHECKPOINT]
    done = rig.store.journal_entry(entry.id)
    assert done is not None and done.outcome is JournalOutcome.COMPLETED
    assert done.result is not None
    document = done.result[RESULT_OUTCOME_DOCUMENT]
    assert isinstance(document, dict)
    assert document["checkpoint"]["kind"] == "awaits_human"  # pyright: ignore[reportUnknownVariableType]
    assert len(rig.store.verdicts(PROJECT)) == 1, "the review behind the checkpoint"
    assert _unrouted_ids(rig) == [entry.id]


def test_a_failed_run_blocks_on_a_human_and_is_left_for_routing(
    rig: DispatchRig,
) -> None:
    node = _launched(rig)
    entry = rig.run_of(node)

    rig.end_run(
        node,
        RunOutcome.FAILED,
        failure={"kind": "cost_cap", "step": "implement-6", "message": "cap hit"},
        reviews=[],
    )

    assert _open_blocks(rig, node) == [BlockedKind.HUMAN]
    assert _unrouted_ids(rig) == [entry.id]
    _no_new_work(rig, node)
    assert _unrouted_ids(rig) == [entry.id], "nothing routes it but a decision"

    route_outcome(rig.store, PROJECT, node.id, entry.id)

    assert _unrouted_ids(rig) == []


def test_a_completed_run_with_an_unknown_review_blocks_and_is_left_for_routing(
    rig: DispatchRig,
) -> None:
    node = _launched(rig)
    entry = rig.run_of(node)

    rig.end_run(node, RunOutcome.COMPLETED, **missing_file_review().document)

    assert _open_blocks(rig, node) == [BlockedKind.HUMAN]
    [message] = rig.store.messages(PROJECT, channel=Channel.ESCALATION)
    assert dict(message.payload or {})[PAYLOAD_FAULT_KIND] == (
        FaultKind.REVIEW_UNKNOWN.value
    )
    done = rig.store.journal_entry(entry.id)
    assert done is not None and done.result is not None
    assert "missing" in str(done.result[RESULT_REVIEW_FAULT])
    assert done.result[RESULT_VERDICT_IDS] == []
    assert _unrouted_ids(rig) == [entry.id]

    route_outcome(rig.store, PROJECT, node.id, entry.id)

    assert _unrouted_ids(rig) == []


def test_a_clean_completed_run_leaves_its_step_waiting_for_routing(
    rig: DispatchRig,
) -> None:
    node = _launched(rig)
    review = single_review(CF_SLUG)
    _write(rig, review)
    entry = rig.run_of(node)

    rig.end_run(node, RunOutcome.COMPLETED, **review.document)

    assert rig.status(node) is NodeStatus.RUNNABLE, "no `started`, no `done`"
    assert _open_blocks(rig, node) == []
    assert _unrouted_ids(rig) == [entry.id]
    _no_new_work(rig, node)

    route_outcome(rig.store, PROJECT, node.id, entry.id)

    assert _unrouted_ids(rig) == []
