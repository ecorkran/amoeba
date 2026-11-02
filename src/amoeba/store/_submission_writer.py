"""The store's one internal inbox-submission writer.

Every ``inbox_submissions`` row is inserted here — by ``apply_submission`` for a
submission that arrived, and by ``submit_answer`` for the one the answerer
makes. One writer keeps the row's shape in one place.

A base class, like ``BlockWriter``, so neither operation class imports the
other.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from amoeba.store import sql_inbox
from amoeba.store._base import StoreBase
from amoeba.store.inbox_models import SubmissionKind, SubmissionOutcome


class SubmissionWriter(StoreBase):
    """Inserts one submission row. Opens no transaction and never commits."""

    def _insert_submission(
        self,
        *,
        submission_id: str,
        project_id: str,
        kind: SubmissionKind,
        submitted_by: str,
        submitted_at: str,
        payload: Mapping[str, object],
        outcome: SubmissionOutcome,
        reason: str | None,
        applied_at: str,
    ) -> None:
        """Insert the row inside the caller's transaction.

        ``submitted_at`` and ``applied_at`` are already rendered for storage.
        """
        self._execute(
            sql_inbox.INSERT_SUBMISSION,
            (
                submission_id,
                project_id,
                kind.value,
                submitted_by,
                submitted_at,
                json.dumps(dict(payload)),
                outcome.value,
                reason,
                applied_at,
            ),
        )
