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
)
from runner.tick_support import PROJECT

EARLY = "2026-10-25T00:00:00+00:00"
LATE = "2026-10-25T00:01:00+00:00"


def _apply(store: Store, context: NodeContext | None = None) -> bool:
    return apply_pending_resolutions(store, PROJECT, context or NodeContext())


def test_an_applied_and_a_rejected_resolution_are_each_answered_with_their_effect(
    store: Store,
) -> None:
    paused = design_step(store)
    finished_run(store, paused, RunOutcome.PAUSED, document=paused_document("r1"))
    applied_id = block_and_resolve(store, paused, "resume", "narrow it")
    completed = design_step(store)
    finished_run(store, completed, RunOutcome.COMPLETED)
    relaunch_id = block_and_resolve(store, completed, "resume")
    fresh = design_step(store)
    rejected_id = block_and_resolve(store, fresh, "retry")

    assert _apply(store) is True

    applied = store.blocked_state(applied_id)
    assert applied is not None and applied.runner_outcome is ResolutionOutcome.APPLIED
    relaunch = store.blocked_state(relaunch_id)
    assert relaunch is not None
    assert relaunch.runner_outcome is ResolutionOutcome.APPLIED
    rejected = store.blocked_state(rejected_id)
    assert rejected is not None
    assert rejected.runner_outcome is ResolutionOutcome.REJECTED
    assert rejected.runner_code == ResolutionRejection.UNKNOWN_DECISION
    assert store.pending_resolutions(PROJECT) == []


def test_a_rejections_new_block_is_open_and_lists_what_is_allowed(
    store: Store,
) -> None:
    node = design_step(store)
    block_and_resolve(store, node, "retry")

    _apply(store)

    opened = store.blocked_state_for(node.id)
    assert opened is not None
    assert opened.context == "resolution rejected: unknown_decision"
    [message] = [
        m
        for m in store.messages(PROJECT, channel=Channel.ESCALATION)
        if m.blocked_state_id == opened.id
    ]
    assert message.payload is not None
    assert message.payload[PAYLOAD_ALLOWED] == ["resume", "stop"]
    current = store.get_node(node.id)
    assert current is not None and current.status is NodeStatus.BLOCKED_ON_HUMAN


def test_resolutions_are_answered_oldest_first(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    later = block_and_resolve(store, design_step(store), "resume")
    earlier = block_and_resolve(store, design_step(store), "resume")
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
    block_and_resolve(store, design_step(store), "resume")
    assert _apply(store) is True

    assert _apply(store) is False


def test_the_node_is_in_context_while_its_resolution_is_answered(
    store: Store,
) -> None:
    node = design_step(store)
    block_and_resolve(store, node, "resume")
    context = NodeContext()

    _apply(store, context)

    assert context.node_id == node.id


def test_instructions_with_no_run_to_resume_are_rejected(store: Store) -> None:
    node = design_step(store)
    state_id = block_and_resolve(store, node, "resume", "narrow it")

    _apply(store)

    state = store.blocked_state(state_id)
    assert state is not None
    assert state.runner_code == ResolutionRejection.INSTRUCTIONS_NOT_APPLICABLE
