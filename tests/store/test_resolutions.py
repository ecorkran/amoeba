"""The store's answer to resolutions: pending, acknowledge, and by-id reads (D9)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from amoeba.store import (
    BlockedKind,
    BlockEffect,
    InvalidTransitionError,
    NodeKind,
    NodeStatus,
    ResolutionOutcome,
    StatusEffect,
    Store,
    sql,
)
from amoeba.store.inbox_models import (
    RESOLUTION_BLOCKED_STATE_ID,
    RESOLUTION_DECISION,
    RESOLUTION_DETAIL,
    SubmissionKind,
)
from amoeba.store.journal_models import CommandKind

PROJECT = "demo"
OTHER_PROJECT = "other"
FIRST_AT = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


def _blocked_node(store: Store, project_id: str = PROJECT) -> tuple[str, str]:
    """A slice node with an open human block: (node id, blocked state id)."""
    node = store.create_node(project_id=project_id, kind=NodeKind.SLICE, title="s")
    return node.id, store.block(node.id, kind=BlockedKind.HUMAN, context="decide").id


def _submit(store: Store, blocked_state_id: str, *, project_id: str = PROJECT) -> None:
    store.apply_submission(
        submission_id=f"s-{blocked_state_id}",
        project_id=project_id,
        kind=SubmissionKind.RESOLUTION,
        submitted_by="pm",
        submitted_at=FIRST_AT,
        payload={
            RESOLUTION_BLOCKED_STATE_ID: blocked_state_id,
            RESOLUTION_DETAIL: "go",
            RESOLUTION_DECISION: "rerun",
        },
    )


def _resolved_node(store: Store, project_id: str = PROJECT) -> tuple[str, str]:
    node_id, blocked_id = _blocked_node(store, project_id)
    _submit(store, blocked_id, project_id=project_id)
    return node_id, blocked_id


def test_pending_resolutions_are_oldest_first(store: Store) -> None:
    _, later = _resolved_node(store)
    _, earlier = _resolved_node(store)
    # The inbox stamps the clock; pin the order the test means.
    with sqlite3.connect(store.path) as connection:
        for state_id, offset in ((earlier, 0), (later, 60)):
            connection.execute(
                f"UPDATE {sql.TABLE_BLOCKED_STATES} SET {sql.COL_BLOCKED_RESOLVED_AT}"
                f" = ? WHERE {sql.COL_BLOCKED_ID} = ?",
                ((FIRST_AT + timedelta(seconds=offset)).isoformat(), state_id),
            )

    assert [s.id for s in store.pending_resolutions(PROJECT)] == [earlier, later]


def test_pending_resolutions_are_scoped_to_the_project(store: Store) -> None:
    _, mine = _resolved_node(store)
    _resolved_node(store, OTHER_PROJECT)

    assert [s.id for s in store.pending_resolutions(PROJECT)] == [mine]


def test_an_unresolved_block_and_the_runners_own_resolve_are_not_pending(
    store: Store,
) -> None:
    _blocked_node(store)
    own, _ = _blocked_node(store)
    store.resolve(own, resolved_by="runner", detail="routed")

    assert store.pending_resolutions(PROJECT) == []


def test_applied_with_no_effect_clears_the_flag_and_records_the_answer(
    store: Store,
) -> None:
    node_id, blocked_id = _resolved_node(store)

    store.acknowledge_resolution(blocked_id, outcome=ResolutionOutcome.APPLIED)

    state = store.blocked_state(blocked_id)
    assert state is not None
    assert state.awaits_runner is False
    assert state.runner_outcome is ResolutionOutcome.APPLIED
    assert state.runner_code is None and state.runner_reason is None
    node = store.get_node(node_id)
    assert node is not None and node.status is NodeStatus.RUNNABLE
    assert store.pending_resolutions(PROJECT) == []


def test_applied_with_a_done_effect_marks_the_node_done(store: Store) -> None:
    node_id, blocked_id = _resolved_node(store)

    store.acknowledge_resolution(
        blocked_id,
        outcome=ResolutionOutcome.APPLIED,
        effect=StatusEffect(NodeStatus.DONE),
    )

    node = store.get_node(node_id)
    assert node is not None and node.status is NodeStatus.DONE


def test_rejected_with_a_block_effect_blocks_again_and_the_new_block_is_open(
    store: Store,
) -> None:
    node_id, blocked_id = _resolved_node(store)

    store.acknowledge_resolution(
        blocked_id,
        outcome=ResolutionOutcome.REJECTED,
        code="decision_required",
        reason="name a decision",
        effect=BlockEffect("resolution rejected: decision_required", {"code": "x"}),
    )

    old = store.blocked_state(blocked_id)
    assert old is not None
    assert old.runner_outcome is ResolutionOutcome.REJECTED
    assert old.runner_code == "decision_required"
    assert old.runner_reason == "name a decision"
    opened = store.blocked_state_for(node_id)
    assert opened is not None and opened.id != blocked_id
    assert opened.context == "resolution rejected: decision_required"
    node = store.get_node(node_id)
    assert node is not None and node.status is NodeStatus.BLOCKED_ON_HUMAN


@pytest.mark.parametrize(
    ("outcome", "code", "reason"),
    [
        (ResolutionOutcome.REJECTED, None, None),
        (ResolutionOutcome.REJECTED, "c", None),
        (ResolutionOutcome.REJECTED, None, "r"),
        (ResolutionOutcome.APPLIED, "c", None),
        (ResolutionOutcome.APPLIED, None, "r"),
    ],
)
def test_the_argument_rules(
    store: Store, outcome: ResolutionOutcome, code: str | None, reason: str | None
) -> None:
    _, blocked_id = _resolved_node(store)

    with pytest.raises(ValueError, match="resolution takes"):
        store.acknowledge_resolution(
            blocked_id, outcome=outcome, code=code, reason=reason
        )

    assert [s.id for s in store.pending_resolutions(PROJECT)] == [blocked_id]


def test_acknowledging_twice_raises(store: Store) -> None:
    _, blocked_id = _resolved_node(store)
    store.acknowledge_resolution(blocked_id, outcome=ResolutionOutcome.APPLIED)

    with pytest.raises(InvalidTransitionError):
        store.acknowledge_resolution(blocked_id, outcome=ResolutionOutcome.APPLIED)


def test_an_unresolved_or_unknown_block_cannot_be_acknowledged(store: Store) -> None:
    _, open_id = _blocked_node(store)

    for target in (open_id, "no-such-state"):
        with pytest.raises(InvalidTransitionError):
            store.acknowledge_resolution(target, outcome=ResolutionOutcome.APPLIED)


def test_a_failing_effect_leaves_the_flag_set_and_writes_nothing(
    store: Store,
) -> None:
    node_id, blocked_id = _resolved_node(store)
    store.journal_issue(
        node_id,
        kind=CommandKind.CF_WRITE,
        parameters={"project": "p", "expected": {}, "checkout": "/w"},
    )

    with pytest.raises(InvalidTransitionError, match="unresolved"):
        store.acknowledge_resolution(
            blocked_id,
            outcome=ResolutionOutcome.APPLIED,
            effect=StatusEffect(NodeStatus.DONE),
        )

    state = store.blocked_state(blocked_id)
    assert state is not None
    assert state.awaits_runner is True
    assert state.runner_outcome is None
    node = store.get_node(node_id)
    assert node is not None and node.status is NodeStatus.RUNNABLE


def test_blocked_state_reads_through_a_read_only_store(store: Store) -> None:
    _, blocked_id = _resolved_node(store)

    with Store.open_read_only(store.path) as reader:
        state = reader.blocked_state(blocked_id)
        missing = reader.blocked_state("no-such-state")

    assert state is not None and state.awaits_runner is True
    assert missing is None


def test_the_pending_query_uses_the_partial_index(store: Store) -> None:
    # The store's connection is private, so a plain one reads the same file.
    with sqlite3.connect(store.path) as connection:
        steps = connection.execute(
            f"EXPLAIN QUERY PLAN {sql.SELECT_PENDING_RESOLUTIONS}", (PROJECT,)
        ).fetchall()

    assert any(sql.INDEX_BLOCKED_AWAITS_RUNNER in str(step[-1]) for step in steps)
