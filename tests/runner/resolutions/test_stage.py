"""``apply_pending_resolutions`` against a real store."""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from amoeba.process import RunOutcome
from amoeba.runner.faults import NodeContext
from amoeba.runner.resolutions.stage import apply_pending_resolutions
from amoeba.runner.resolutions.vocabulary import PAYLOAD_ALLOWED, ResolutionRejection
from amoeba.store import Channel, NodeStatus, ResolutionOutcome, Store
from runner.resolutions.resolution_support import (
    block_and_resolve,
    design_step,
    finished_run,
    paused_document,
    tree_of,
)
from runner.tick_support import PROJECT

EARLY = "2026-10-25T00:00:00+00:00"
LATE = "2026-10-25T00:01:00+00:00"


def _apply(store: Store, context: NodeContext | None = None) -> bool:
    return apply_pending_resolutions(
        store, PROJECT, tree_of(store), context or NodeContext()
    )


def test_an_applied_and_a_rejected_resolution_are_each_answered_with_their_effect(
    store: Store,
) -> None:
    paused = design_step(store)
    finished_run(store, paused, RunOutcome.PAUSED, document=paused_document("r1"))
    applied_id = block_and_resolve(store, paused, "retry", "narrow it")
    completed = design_step(store)
    finished_run(store, completed, RunOutcome.COMPLETED)
    accepted_id = block_and_resolve(store, completed, "accept")
    fresh = design_step(store)
    rejected_id = block_and_resolve(store, fresh, "retry")

    assert _apply(store) is True

    applied = store.blocked_state(applied_id)
    assert applied is not None and applied.runner_outcome is ResolutionOutcome.APPLIED
    done = store.get_node(completed.id)
    assert done is not None and done.status is NodeStatus.DONE
    accepted = store.blocked_state(accepted_id)
    assert accepted is not None
    assert accepted.runner_outcome is ResolutionOutcome.APPLIED
    rejected = store.blocked_state(rejected_id)
    assert rejected is not None
    assert rejected.runner_outcome is ResolutionOutcome.REJECTED
    assert rejected.runner_code == ResolutionRejection.DECISION_NOT_APPLICABLE
    assert store.pending_resolutions(PROJECT) == []


def test_a_rejections_new_block_is_open_and_lists_what_is_allowed(
    store: Store,
) -> None:
    node = design_step(store)
    block_and_resolve(store, node, "retry")

    _apply(store)

    opened = store.blocked_state_for(node.id)
    assert opened is not None
    assert opened.context == "resolution rejected: decision_not_applicable"
    [message] = [
        m
        for m in store.messages(PROJECT, channel=Channel.ESCALATION)
        if m.blocked_state_id == opened.id
    ]
    assert message.payload is not None
    assert message.payload[PAYLOAD_ALLOWED] == ["rerun", "stop"]
    current = store.get_node(node.id)
    assert current is not None and current.status is NodeStatus.BLOCKED_ON_HUMAN


def test_resolutions_are_answered_oldest_first(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    later = block_and_resolve(store, design_step(store), "rerun")
    earlier = block_and_resolve(store, design_step(store), "rerun")
    # The inbox stamps the clock; pin the order the test means.
    with sqlite3.connect(store.path) as connection:
        for state_id, stamp in (
            (earlier, "2026-10-25T00:00:00+00:00"),
            (later, "2026-10-25T00:01:00+00:00"),
        ):
            connection.execute(
                "UPDATE blocked_states SET resolved_at = ? WHERE id = ?",
                (stamp, state_id),
            )
    order: list[str] = []
    real = store.acknowledge_resolution

    def spy(blocked_state_id: str, **kwargs: Any) -> None:
        order.append(blocked_state_id)
        real(blocked_state_id, **kwargs)

    monkeypatch.setattr(store, "acknowledge_resolution", spy)

    _apply(store)

    assert order == [earlier, later]


def test_a_second_call_does_nothing(store: Store) -> None:
    block_and_resolve(store, design_step(store), "rerun")
    assert _apply(store) is True

    assert _apply(store) is False


def test_the_node_is_in_context_while_its_resolution_is_answered(
    store: Store,
) -> None:
    node = design_step(store)
    block_and_resolve(store, node, "rerun")
    context = NodeContext()

    _apply(store, context)

    assert context.node_id == node.id


def test_a_poisoned_document_is_rejected_not_raised(store: Store) -> None:
    node = design_step(store)
    finished_run(
        store, node, RunOutcome.PAUSED, document={"run_id": "r", "outcome": "nonsense"}
    )
    state_id = block_and_resolve(store, node, "retry")

    _apply(store)

    state = store.blocked_state(state_id)
    assert state is not None
    assert state.runner_code == ResolutionRejection.CHECKPOINT_UNKNOWN
