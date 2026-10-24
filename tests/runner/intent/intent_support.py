"""Submit intents to a store, the way the inbox does."""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import count
from typing import Any

from amoeba.store import Store
from amoeba.store.inbox_models import SubmissionKind

_SUBMISSIONS = count(1)


def submit(
    store: Store,
    body: dict[str, Any],
    *,
    node_id: str | None = None,
    project_id: str = "demo",
) -> str:
    """Apply an intent submission and return the id of the message it created."""
    submission_id = f"sub-{next(_SUBMISSIONS)}"
    store.apply_submission(
        submission_id=submission_id,
        project_id=project_id,
        kind=SubmissionKind.INTENT,
        submitted_by="pm",
        submitted_at=datetime(2026, 10, 23, tzinfo=UTC),
        payload={"node_id": node_id, "body": body},
    )
    intent = store.intent_for_submission(submission_id)
    assert intent is not None
    return intent.id
