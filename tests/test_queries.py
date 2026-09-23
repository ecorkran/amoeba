"""Tests for block/resolve and the two Runner queries.

This is the checkpoint mechanic end to end — the claim the slice exists to make:
a blocked node leaves the runnable set, appears in the blocked set with its
blocker identified, and returns to runnable when, and only when, its resolution
slot is filled.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.store.models import (
    BLOCKED_KIND_TO_STATUS,
    BLOCKED_STATUSES,
    BlockedKind,
    InvalidTransitionError,
    NodeKind,
    NodeNotFoundError,
    NodeStatus,
)
from amoeba.store.store import Store


def _make_node(store: Store, project_id: str = "demo", title: str = "a slice") -> str:
    return store.create_node(project_id=project_id, kind=NodeKind.SLICE, title=title).id


def test_blocking_removes_from_runnable_and_names_the_blocker(
    store_file: Path,
) -> None:
    """The observable claim, in one test."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)
        assert [node.id for node in store.runnable("demo")] == [node_id]

        store.block(node_id, kind=BlockedKind.HUMAN, context="awaiting PM ruling")

        assert store.runnable("demo") == []
        blocked = store.blocked("demo")
        assert len(blocked) == 1
        assert blocked[0].node.id == node_id
        assert blocked[0].blocked_state.kind is BlockedKind.HUMAN
        assert blocked[0].blocked_state.context == "awaiting PM ruling"
        assert not blocked[0].blocked_state.is_resolved


def test_node_returns_to_runnable_only_when_resolved(store_file: Path) -> None:
    """An unfilled slot keeps the node blocked; filling it releases the node."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)
        store.block(node_id, kind=BlockedKind.JUDGE, context="needs a verdict")

        assert store.runnable("demo") == []

        resolved = store.resolve(node_id, resolved_by="judge", detail="verdict: pass")

        assert resolved.is_resolved
        assert resolved.resolution is not None
        assert resolved.resolution.resolved_by == "judge"
        assert resolved.resolution.detail == "verdict: pass"
        assert [node.id for node in store.runnable("demo")] == [node_id]
        assert store.blocked("demo") == []


@pytest.mark.parametrize("kind", list(BlockedKind), ids=lambda arg: str(arg))
def test_every_blocker_kind_round_trips(store_file: Path, kind: BlockedKind) -> None:
    """Each blocker kind sets its matching status and is returned by the query."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)

        store.block(node_id, kind=kind, context=f"blocked on {kind.value}")

        node = store.get_node(node_id)
        assert node is not None
        assert node.status is BLOCKED_KIND_TO_STATUS[kind]
        assert node.status in BLOCKED_STATUSES

        blocked = store.blocked("demo")
        assert [entry.blocked_state.kind for entry in blocked] == [kind]


@pytest.mark.parametrize("status", sorted(BLOCKED_STATUSES), ids=lambda arg: str(arg))
def test_blocked_query_covers_every_blocked_status(
    store_file: Path, status: NodeStatus
) -> None:
    """The blocked query is parametrized across every blocked_on_* value."""
    kind = next(
        blocker
        for blocker, mapped in BLOCKED_KIND_TO_STATUS.items()
        if mapped is status
    )

    with Store.open(store_file) as store:
        node_id = _make_node(store)
        store.block(node_id, kind=kind, context="ctx")

        blocked = store.blocked("demo")

        assert [entry.node.status for entry in blocked] == [status]


def test_blocking_an_already_blocked_node_raises(store_file: Path) -> None:
    """An existing block is never silently overwritten."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)
        store.block(node_id, kind=BlockedKind.HUMAN, context="first")

        with pytest.raises(InvalidTransitionError, match="already blocked"):
            store.block(node_id, kind=BlockedKind.JUDGE, context="second")


def test_resolving_an_unblocked_node_raises(store_file: Path) -> None:
    """Resolving a node that is not blocked raises rather than no-opping."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)

        with pytest.raises(InvalidTransitionError, match="not blocked"):
            store.resolve(node_id, resolved_by="pm", detail="nothing to resolve")


def test_blocking_an_unknown_node_raises(store_file: Path) -> None:
    """Blocking a node that does not exist raises."""
    with Store.open(store_file) as store:
        with pytest.raises(NodeNotFoundError):
            store.block("no-such-node", kind=BlockedKind.HUMAN, context="ctx")


def test_status_and_blocked_state_never_disagree(store_file: Path) -> None:
    """After every operation, status and blocked-state stay consistent."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)

        store.block(node_id, kind=BlockedKind.SQ_CHECKPOINT, context="awaiting sq")
        node = store.get_node(node_id)
        assert node is not None
        assert node.status in BLOCKED_STATUSES
        open_state = store.blocked_state_for(node_id)
        assert open_state is not None and not open_state.is_resolved

        store.resolve(node_id, resolved_by="sq", detail="run finished")
        node = store.get_node(node_id)
        assert node is not None
        assert node.status is NodeStatus.RUNNABLE
        assert store.blocked_state_for(node_id) is None


def test_failed_operation_leaves_state_consistent(store_file: Path) -> None:
    """A rejected second block changes nothing about the first."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)
        store.block(node_id, kind=BlockedKind.HUMAN, context="first")

        with pytest.raises(InvalidTransitionError):
            store.block(node_id, kind=BlockedKind.JUDGE, context="second")

        node = store.get_node(node_id)
        assert node is not None
        assert node.status is NodeStatus.BLOCKED_ON_HUMAN
        states = list(store.all_blocked_states(node_id))
        assert len(states) == 1
        assert states[0].context == "first"


def test_a_node_can_be_blocked_again_after_resolution(store_file: Path) -> None:
    """Resolution closes one block; the node can enter a new one afterwards."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)

        store.block(node_id, kind=BlockedKind.HUMAN, context="first")
        store.resolve(node_id, resolved_by="pm", detail="ruled")
        store.block(node_id, kind=BlockedKind.JUDGE, context="second")

        blocked = store.blocked("demo")
        assert [entry.blocked_state.context for entry in blocked] == ["second"]
        assert len(list(store.all_blocked_states(node_id))) == 2


def test_runnable_is_project_scoped_against_a_populated_second_project(
    store_file: Path,
) -> None:
    """Functional Requirement 6 for the runnable query, asserted directly."""
    with Store.open(store_file) as store:
        alpha_runnable = _make_node(store, project_id="alpha", title="alpha runnable")
        alpha_blocked = _make_node(store, project_id="alpha", title="alpha blocked")
        beta_runnable = _make_node(store, project_id="beta", title="beta runnable")
        beta_blocked = _make_node(store, project_id="beta", title="beta blocked")

        store.block(alpha_blocked, kind=BlockedKind.HUMAN, context="alpha ctx")
        store.block(beta_blocked, kind=BlockedKind.JUDGE, context="beta ctx")

        assert [node.id for node in store.runnable("alpha")] == [alpha_runnable]
        assert [node.id for node in store.runnable("beta")] == [beta_runnable]


def test_blocked_is_project_scoped_against_a_populated_second_project(
    store_file: Path,
) -> None:
    """Functional Requirement 6 for the blocked query, asserted directly."""
    with Store.open(store_file) as store:
        _make_node(store, project_id="alpha", title="alpha runnable")
        alpha_blocked = _make_node(store, project_id="alpha", title="alpha blocked")
        _make_node(store, project_id="beta", title="beta runnable")
        beta_blocked = _make_node(store, project_id="beta", title="beta blocked")

        store.block(alpha_blocked, kind=BlockedKind.HUMAN, context="alpha ctx")
        store.block(beta_blocked, kind=BlockedKind.JUDGE, context="beta ctx")

        alpha = store.blocked("alpha")
        beta = store.blocked("beta")

        assert [entry.node.id for entry in alpha] == [alpha_blocked]
        assert [entry.blocked_state.context for entry in alpha] == ["alpha ctx"]
        assert [entry.node.id for entry in beta] == [beta_blocked]
        assert [entry.blocked_state.context for entry in beta] == ["beta ctx"]


def test_both_queries_empty_cases(store_file: Path) -> None:
    """Both Runner queries return empty lists, not errors, when there is none."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)

        assert store.blocked("demo") == []

        store.block(node_id, kind=BlockedKind.HUMAN, context="ctx")

        assert store.runnable("demo") == []


def test_blocked_query_answers_on_whom_without_a_second_call(
    store_file: Path,
) -> None:
    """Each blocked result already carries its blocked-state record."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)
        store.block(node_id, kind=BlockedKind.JUDGE, context="needs a verdict")

        entry = store.blocked("demo")[0]

        assert entry.blocked_state.node_id == entry.node.id
        assert entry.blocked_state.kind is BlockedKind.JUDGE
        assert entry.blocked_state.context == "needs a verdict"


def test_non_runnable_statuses_are_absent_from_runnable(store_file: Path) -> None:
    """Only runnable nodes appear — in_progress and done do not."""
    with Store.open(store_file) as store:
        runnable_id = _make_node(store, title="runnable")
        in_progress = _make_node(store, title="in progress")
        done = _make_node(store, title="done")

        store.update_node_status(in_progress, NodeStatus.IN_PROGRESS)
        store.update_node_status(done, NodeStatus.DONE)

        assert [node.id for node in store.runnable("demo")] == [runnable_id]


def test_block_accepts_an_optional_payload(store_file: Path) -> None:
    """``payload`` is accepted without changing what ``block()`` does.

    Acceptance only: ``blocked_states`` has no payload column, and the payload
    becomes readable on the escalation row, where its round trip is tested.
    """
    with Store.open(store_file) as store:
        node_id = _make_node(store)

        blocked = store.block(
            node_id,
            kind=BlockedKind.HUMAN,
            context="needs a decision",
            payload={"options": ["a", "b"]},
        )

        node = store.get_node(node_id)
        assert blocked.node_id == node_id
        assert node is not None
        assert node.status is NodeStatus.BLOCKED_ON_HUMAN
