"""Shared helpers for change-feed tests."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime

from amoeba.process.recovery import reconcile
from amoeba.store import CommandKind, Store, SubmissionKind, SubmissionRecord, sql_feed
from amoeba.store.feed_models import Change
from amoeba.store.inbox_models import (
    INTENT_BODY,
    INTENT_NODE_ID,
    RESOLUTION_BLOCKED_STATE_ID,
    RESOLUTION_DETAIL,
)
from amoeba.store.mapping_feed import map_change


def raw_changes(store: Store, project_id: str) -> list[Change]:
    """Every change for a project, in ``seq`` order, read on a second connection."""
    columns = ", ".join(sql_feed.CHANGE_COLUMNS)
    with sqlite3.connect(store.path) as connection:
        rows = connection.execute(
            f"SELECT {columns} FROM {sql_feed.TABLE_CHANGES} "
            f"WHERE {sql_feed.COL_CHANGE_PROJECT_ID} = ? "
            f"ORDER BY {sql_feed.COL_CHANGE_SEQ}",
            (project_id,),
        ).fetchall()
    return [map_change(row) for row in rows]


SUBMITTED_AT = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
ESCALATION_PARAMETERS: dict[str, object] = {"project": "p", "expected": {}}


def apply(
    store: Store,
    submission_id: str,
    kind: SubmissionKind,
    payload: Mapping[str, object],
    project_id: str,
) -> SubmissionRecord:
    """Apply one submission through the store's real inbox path."""
    return store.apply_submission(
        submission_id=submission_id,
        project_id=project_id,
        kind=kind,
        submitted_by="tester",
        submitted_at=SUBMITTED_AT,
        payload=payload,
    )


def post_intent(
    store: Store, submission_id: str, node_id: str, project_id: str
) -> None:
    payload = {INTENT_NODE_ID: node_id, INTENT_BODY: {"want": "a thing"}}
    apply(store, submission_id, SubmissionKind.INTENT, payload, project_id)


def resolve_by_submission(
    store: Store, submission_id: str, node_id: str, project_id: str
) -> None:
    """Resolve a node's open block the way a human reply does."""
    blocked = store.blocked_state_for(node_id)
    assert blocked is not None
    payload = {RESOLUTION_BLOCKED_STATE_ID: blocked.id, RESOLUTION_DETAIL: "go"}
    apply(store, submission_id, SubmissionKind.RESOLUTION, payload, project_id)


def escalate_by_recovery(store: Store, node_id: str, project_id: str) -> None:
    """Stage an entry with no observer and reconcile: recovery escalates it."""
    store.journal_issue(
        node_id, kind=CommandKind.CF_WRITE, parameters=ESCALATION_PARAMETERS
    )
    reconcile(store, project_id, {})
