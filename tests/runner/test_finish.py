"""Recording a finished run against a real temporary store."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from amoeba.process import RunCheckpoint, RunOutcome, RunOutcomeDocument
from amoeba.runner.faults import LaunchFailure
from amoeba.runner.finish import RESULT_RUN_ID, record
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.runner.observed import LaunchFailed, RunEnded, RunVanished
from amoeba.store import (
    PARAM_RUN_ID,
    BlockedKind,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
    Node,
    NodeKind,
    NodeStatus,
    Store,
)
from runner.observe_support import document

PROJECT = "demo"
RUN_ID = "run-1"


@pytest.fixture
def node(store: Store) -> Node:
    return store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")


@pytest.fixture
def entry(store: Store, node: Node) -> JournalEntry:
    return store.journal_issue(
        node.id,
        kind=CommandKind.SQ_RUN,
        parameters={PARAM_PIPELINE: "noop", PARAM_PARAMS: {}, PARAM_RUN_ID: RUN_ID},
    )


def _resolved(store: Store, entry: JournalEntry) -> JournalEntry:
    reloaded = store.journal_entry(entry.id)
    assert reloaded is not None
    return reloaded


def _open_blocks(store: Store, node: Node) -> list[BlockedKind]:
    return [s.kind for s in store.all_blocked_states(node.id) if not s.is_resolved]


def test_completed_resolves_completed_and_blocks_nothing(
    store: Store, node: Node, entry: JournalEntry
) -> None:
    record(store, entry, RunEnded(document(RUN_ID, RunOutcome.COMPLETED)))

    done = _resolved(store, entry)
    assert (done.outcome, done.resolved_by) == (
        JournalOutcome.COMPLETED,
        JournalResolver.ISSUER,
    )
    assert done.result == {
        RESULT_RUN_ID: RUN_ID,
        "outcome": "completed",
        "status": "completed",
    }
    assert _open_blocks(store, node) == []


def test_failed_blocks_on_a_human_then_resolves_completed(
    store: Store, node: Node, entry: JournalEntry
) -> None:
    record(store, entry, RunEnded(document(RUN_ID, RunOutcome.FAILED)))

    done = _resolved(store, entry)
    assert done.outcome is JournalOutcome.COMPLETED
    assert done.result is not None and done.result["outcome"] == "failed"
    assert _open_blocks(store, node) == [BlockedKind.HUMAN]
    blocked_node = store.get_node(node.id)
    assert blocked_node is not None
    assert blocked_node.status is NodeStatus.BLOCKED_ON_HUMAN


def test_paused_records_the_checkpoint_as_reported(
    store: Store, node: Node, entry: JournalEntry
) -> None:
    paused_at = datetime(2026, 10, 23, 9, 30, tzinfo=UTC)
    doc = RunOutcomeDocument(
        run_id=RUN_ID,
        outcome=RunOutcome.PAUSED,
        status="paused",
        checkpoint=RunCheckpoint(paused_at=paused_at),
    )

    record(store, entry, RunEnded(doc))

    done = _resolved(store, entry)
    assert done.outcome is JournalOutcome.COMPLETED
    assert done.result is not None
    assert done.result["checkpoint"] == {"paused_at": paused_at.isoformat()}
    assert _open_blocks(store, node) == [BlockedKind.HUMAN]


def test_orphaned_blocks_and_resolves_failed(
    store: Store, node: Node, entry: JournalEntry
) -> None:
    record(store, entry, RunEnded(document(RUN_ID, RunOutcome.ORPHANED)))

    assert _resolved(store, entry).outcome is JournalOutcome.FAILED
    assert _open_blocks(store, node) == [BlockedKind.HUMAN]


def test_a_vanished_run_blocks_and_resolves_failed(
    store: Store, node: Node, entry: JournalEntry
) -> None:
    record(store, entry, RunVanished())

    done = _resolved(store, entry)
    assert done.outcome is JournalOutcome.FAILED
    assert done.result == {RESULT_RUN_ID: RUN_ID, "outcome": "vanished"}
    assert _open_blocks(store, node) == [BlockedKind.HUMAN]


def test_a_failed_launch_blocks_with_the_reason_code_and_tail(
    store: Store, node: Node, entry: JournalEntry
) -> None:
    failed = LaunchFailed(LaunchFailure.EXITED_BEFORE_LINE, 1, "provider unreachable")

    record(store, entry, failed)

    done = _resolved(store, entry)
    assert done.outcome is JournalOutcome.FAILED
    assert done.result == {
        RESULT_RUN_ID: RUN_ID,
        "launch_failure": "exited_before_line",
    }
    blocked = store.blocked_state_for(node.id)
    assert blocked is not None
    assert "exited_before_line" in blocked.context
    assert "exit code 1" in blocked.context
    assert "provider unreachable" in blocked.context


def test_an_unknown_exit_code_is_stated_as_unknown(
    store: Store, node: Node, entry: JournalEntry
) -> None:
    record(store, entry, LaunchFailed(LaunchFailure.SPAWN_ERROR, None, "no sq"))

    blocked = store.blocked_state_for(node.id)
    assert blocked is not None and "exit code unknown" in blocked.context


def test_reentry_after_a_crash_between_block_and_resolve_finishes_the_sequence(
    store: Store, node: Node, entry: JournalEntry
) -> None:
    # The crash: the block was written, the entry was not resolved.
    store.block(node.id, kind=BlockedKind.HUMAN, context="run failed")
    assert not _resolved(store, entry).is_resolved

    record(store, entry, RunEnded(document(RUN_ID, RunOutcome.FAILED)))

    assert _resolved(store, entry).outcome is JournalOutcome.COMPLETED
    assert _open_blocks(store, node) == [BlockedKind.HUMAN], "exactly one block"


def test_a_non_ending_outcome_is_refused(store: Store, entry: JournalEntry) -> None:
    with pytest.raises(ValueError, match="not an end state"):
        record(store, entry, RunEnded(document(RUN_ID, RunOutcome.TIMED_OUT)))
    assert not _resolved(store, entry).is_resolved
