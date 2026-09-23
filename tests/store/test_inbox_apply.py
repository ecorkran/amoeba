"""apply_submission across every kind, every rejection branch, replay, and D4."""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import amoeba.store.inbox as inbox_module
from amoeba.store.inbox import InboxOperations
from amoeba.store.inbox_models import (
    INTENT_BODY,
    INTENT_NODE_ID,
    RESOLUTION_BLOCKED_STATE_ID,
    RESOLUTION_DETAIL,
    Channel,
    SubmissionKind,
    SubmissionOutcome,
    SubmissionRecord,
)
from amoeba.store.models import BlockedKind, NodeKind, NodeStatus
from amoeba.store.store import Store

PROJECT = "demo"
OTHER_PROJECT = "other"
SUBMITTED_AT = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


@pytest.fixture
def store(store_file: Path) -> Iterator[Store]:
    with Store.open(store_file) as opened:
        yield opened


def _node(store: Store, project_id: str = PROJECT) -> str:
    return store.create_node(project_id=project_id, kind=NodeKind.SLICE, title="n").id


def _apply(
    store: Store,
    submission_id: str,
    kind: SubmissionKind,
    payload: Mapping[str, object],
    *,
    submitted_at: datetime = SUBMITTED_AT,
    project_id: str = PROJECT,
) -> SubmissionRecord:
    return store.apply_submission(
        submission_id=submission_id,
        project_id=project_id,
        kind=kind,
        submitted_by="tester",
        submitted_at=submitted_at,
        payload=payload,
    )


def _resolution(blocked_state_id: str) -> dict[str, object]:
    return {RESOLUTION_BLOCKED_STATE_ID: blocked_state_id, RESOLUTION_DETAIL: "go"}


def _intent(node_id: str | None = None) -> dict[str, object]:
    return {INTENT_NODE_ID: node_id, INTENT_BODY: {"want": "a thing"}}


# --------------------------------------------------------------------------
# The kind-to-effect table and the shape of rejection
# --------------------------------------------------------------------------


def test_every_kind_has_an_effect() -> None:
    assert set(InboxOperations.KIND_EFFECTS) == set(SubmissionKind)


def test_no_exception_is_caught_to_implement_a_rejection() -> None:
    """Rejection is an explicit branch. The module has no ``except`` at all."""
    source = Path(inbox_module.__file__).read_text(encoding="utf-8")
    handlers = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ExceptHandler)
    ]
    assert handlers == []


# --------------------------------------------------------------------------
# Replay (D2)
# --------------------------------------------------------------------------


def test_replay_leaves_one_record_and_applies_the_effect_once(store: Store) -> None:
    first = _apply(store, "s-1", SubmissionKind.INTENT, _intent())
    again = _apply(store, "s-1", SubmissionKind.INTENT, _intent())

    assert again == first
    assert len(store.submissions(PROJECT)) == 1
    assert len(store.messages(PROJECT, channel=Channel.INTENT)) == 1


def test_replay_with_different_content_keeps_the_first(store: Store) -> None:
    """First wins. Warning about it is the tenant's job; the store is silent."""
    first = _apply(store, "s-1", SubmissionKind.INTENT, _intent())
    later = _apply(store, "s-1", SubmissionKind.CREATE_PROJECT, {})

    assert later == first
    assert later.kind is SubmissionKind.INTENT


def test_malformed_payload_raises_and_records_nothing(store: Store) -> None:
    with pytest.raises(ValueError, match=RESOLUTION_BLOCKED_STATE_ID):
        _apply(store, "s-1", SubmissionKind.RESOLUTION, {RESOLUTION_DETAIL: "go"})

    assert store.submission("s-1") is None


# --------------------------------------------------------------------------
# create_project
# --------------------------------------------------------------------------


def test_create_project_is_applied(store: Store) -> None:
    record = _apply(store, "s-1", SubmissionKind.CREATE_PROJECT, {})

    assert record.outcome is SubmissionOutcome.APPLIED
    assert record.reason is None


def test_create_project_for_an_existing_project_is_applied_and_changes_nothing(
    store: Store,
) -> None:
    node_id = _node(store)
    _apply(store, "s-1", SubmissionKind.CREATE_PROJECT, {})

    record = _apply(store, "s-2", SubmissionKind.CREATE_PROJECT, {})

    assert record.outcome is SubmissionOutcome.APPLIED
    assert [node.id for node in store.nodes_for_project(PROJECT)] == [node_id]
    assert store.messages(PROJECT, channel=Channel.INTENT) == []


# --------------------------------------------------------------------------
# resolution
# --------------------------------------------------------------------------


def test_resolution_fills_the_slot_and_releases_the_node(store: Store) -> None:
    node_id = _node(store)
    blocked = store.block(node_id, kind=BlockedKind.HUMAN, context="decide")

    record = _apply(store, "s-1", SubmissionKind.RESOLUTION, _resolution(blocked.id))

    resolved = store.blocked_state_for(node_id, include_resolved=True)
    node = store.get_node(node_id)
    assert record.outcome is SubmissionOutcome.APPLIED
    assert resolved is not None and resolved.resolution is not None
    assert resolved.resolution.resolved_by == "tester"
    assert resolved.resolution.detail == "go"
    assert node is not None and node.status is NodeStatus.RUNNABLE


def _assert_rejected(record: SubmissionRecord, fragment: str) -> None:
    assert record.outcome is SubmissionOutcome.REJECTED
    assert record.reason is not None and fragment in record.reason


def test_resolution_of_a_nonexistent_blocked_state_is_rejected(store: Store) -> None:
    record = _apply(store, "s-1", SubmissionKind.RESOLUTION, _resolution("nope"))

    _assert_rejected(record, "does not exist")


def test_resolution_of_an_already_resolved_blocked_state_is_rejected(
    store: Store,
) -> None:
    node_id = _node(store)
    blocked = store.block(node_id, kind=BlockedKind.HUMAN, context="decide")
    store.resolve(node_id, resolved_by="pm", detail="done")

    record = _apply(store, "s-1", SubmissionKind.RESOLUTION, _resolution(blocked.id))

    _assert_rejected(record, "already resolved")


def test_resolution_of_another_projects_blocked_state_is_rejected(
    store: Store,
) -> None:
    node_id = _node(store, project_id=OTHER_PROJECT)
    blocked = store.block(node_id, kind=BlockedKind.HUMAN, context="decide")

    record = _apply(store, "s-1", SubmissionKind.RESOLUTION, _resolution(blocked.id))

    node = store.get_node(node_id)
    _assert_rejected(record, "not in this project")
    assert node is not None and node.status is NodeStatus.BLOCKED_ON_HUMAN


def test_a_stale_reply_does_not_resolve_a_newer_block(store: Store) -> None:
    """Re-blocked since the reply was written: the reply is not redirected."""
    node_id = _node(store)
    original = store.block(node_id, kind=BlockedKind.HUMAN, context="first")
    store.resolve(node_id, resolved_by="pm", detail="done")
    newer = store.block(node_id, kind=BlockedKind.HUMAN, context="second")

    record = _apply(store, "s-1", SubmissionKind.RESOLUTION, _resolution(original.id))

    still_open = store.blocked_state_for(node_id)
    _assert_rejected(record, "already resolved")
    assert still_open is not None and still_open.id == newer.id


# --------------------------------------------------------------------------
# intent
# --------------------------------------------------------------------------


def test_intent_writes_one_unacknowledged_message_with_provenance(
    store: Store,
) -> None:
    node_id = _node(store)

    record = _apply(store, "s-1", SubmissionKind.INTENT, _intent(node_id))

    [message] = store.pending_intents(PROJECT)
    assert record.outcome is SubmissionOutcome.APPLIED
    assert message.submission_id == "s-1"
    assert message.node_id == node_id
    assert message.payload == {"want": "a thing"}
    assert not message.is_acknowledged


def test_intent_without_a_node_is_applied(store: Store) -> None:
    record = _apply(store, "s-1", SubmissionKind.INTENT, _intent())

    [message] = store.pending_intents(PROJECT)
    assert record.outcome is SubmissionOutcome.APPLIED
    assert message.node_id is None


@pytest.mark.parametrize("project_of_node", [None, OTHER_PROJECT])
def test_intent_naming_a_node_outside_this_project_is_rejected(
    store: Store, project_of_node: str | None
) -> None:
    node_id = "missing" if project_of_node is None else _node(store, project_of_node)

    record = _apply(store, "s-1", SubmissionKind.INTENT, _intent(node_id))

    _assert_rejected(record, "does not exist in this project")
    assert store.pending_intents(PROJECT) == []


# --------------------------------------------------------------------------
# Order (D4) and the submissions listing
# --------------------------------------------------------------------------


def test_order_is_apply_order_not_submitted_at(store: Store) -> None:
    """Envelopes stamped newest-first still sequence in the order applied."""
    stamps = [SUBMITTED_AT - timedelta(minutes=minutes) for minutes in (0, 5, 10)]

    for index, stamp in enumerate(stamps):
        _apply(
            store, f"s-{index}", SubmissionKind.INTENT, _intent(), submitted_at=stamp
        )

    records = store.submissions(PROJECT)
    messages = store.messages(PROJECT, channel=Channel.INTENT)
    assert [record.id for record in records] == ["s-0", "s-1", "s-2"]
    assert [record.applied_seq for record in records] == sorted(
        record.applied_seq for record in records
    )
    assert [record.submitted_at for record in records] == stamps
    assert [message.submission_id for message in messages] == ["s-0", "s-1", "s-2"]


def test_submissions_filter_by_outcome_in_applied_order(store: Store) -> None:
    _apply(store, "s-0", SubmissionKind.INTENT, _intent())
    _apply(store, "s-1", SubmissionKind.RESOLUTION, _resolution("nope"))
    _apply(store, "s-2", SubmissionKind.CREATE_PROJECT, {})

    applied = store.submissions(PROJECT, outcome=SubmissionOutcome.APPLIED)
    rejected = store.submissions(PROJECT, outcome=SubmissionOutcome.REJECTED)

    assert [record.id for record in applied] == ["s-0", "s-2"]
    assert [record.id for record in rejected] == ["s-1"]
    assert store.submissions(OTHER_PROJECT) == []


def test_submission_is_none_until_applied(store: Store) -> None:
    assert store.submission("s-1") is None
