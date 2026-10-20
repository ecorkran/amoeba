"""The Runner's one-transaction report of a review it launched.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

A review the Runner launches has three durable effects: the verdict, the
``runner_issued`` ledger row that tells detection the Runner already owns this
file, and the resolution of the journal entry that issued the command. Done as
three calls, a crash between them leaves a verdict with an unresolved entry, or
a resolved entry with no verdict. Here they land together or not at all.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from amoeba.store import sql_inbox
from amoeba.store.evidence_models import VerdictInput, VerdictRecord
from amoeba.store.feed import FeedOperations
from amoeba.store.feed_models import DetectionInput, DetectionOutcome
from amoeba.store.journal import RESULT_KEY_RUN_ID, JournalOperations
from amoeba.store.journal_models import (
    REVIEW_PRODUCING_KINDS,
    JournalOutcome,
    JournalResolver,
)
from amoeba.store.models import InvalidTransitionError, StoreIntegrityError


class RunnerReportOperations(JournalOperations, FeedOperations):
    """``record_runner_report``: verdict, ledger row, and resolution as one commit."""

    def record_runner_report(
        self,
        entry_id: str,
        verdict: VerdictInput,
        detection: DetectionInput,
        *,
        result: Mapping[str, object],
    ) -> VerdictRecord:
        """Record a launched review's verdict and resolve its journal entry.

        One transaction, in this order: the checks, the verdict (with
        ``record_verdict``'s retry rule), the ``runner_issued`` ledger row
        carrying the verdict's id and node, and the entry resolved
        ``completed`` by ``issuer`` with ``result``.

        A ledger key already present (detection got there first) keeps its
        existing row and inserts nothing; the entry is still resolved. A verdict
        id already recorded returns the existing record, and the ledger row and
        resolution still happen.

        Returns:
            The verdict record, new or existing.

        Raises:
            ValueError: ``detection.outcome`` is not ``runner_issued``;
                ``result`` lacks ``run_id``; or the verdict failed its checks.
                Nothing is written.
            InvalidTransitionError: The entry does not exist, is already
                resolved, is not a review-producing kind, or belongs to
                another project than ``detection``. Nothing is written.
            StoreIntegrityError: The verdict is recorded in another project.
                Nothing is written.
        """
        if detection.outcome is not DetectionOutcome.RUNNER_ISSUED:
            raise ValueError(
                f"record_runner_report records a runner_issued review, "
                f"not {detection.outcome.value!r}"
            )
        if RESULT_KEY_RUN_ID not in result:
            raise ValueError(f"result must carry {RESULT_KEY_RUN_ID!r}")

        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            self._require_open_review_entry(entry_id, detection.project_id)
            record = self._record_verdict_within(verdict, detection.project_id)
            if record.project_id != detection.project_id:
                raise StoreIntegrityError(
                    f"verdict {record.id!r} is recorded in project "
                    f"{record.project_id!r}, not {detection.project_id!r}"
                )
            if self._detection_by_key(detection) is None:
                self._insert_detection(
                    dataclasses.replace(
                        detection, verdict_id=record.id, node_id=record.node_id
                    )
                )
            self._resolve_entry_within(
                entry_id, JournalOutcome.COMPLETED, result, JournalResolver.ISSUER
            )
        return record

    def _require_open_review_entry(self, entry_id: str, project_id: str) -> None:
        """Refuse unless the entry is an unresolved review command of the project."""
        entry = self.journal_entry(entry_id)
        if entry is None:
            raise InvalidTransitionError(f"journal entry {entry_id!r} does not exist")
        if entry.is_resolved:
            raise InvalidTransitionError(
                f"journal entry {entry_id!r} is already resolved"
            )
        if entry.kind not in REVIEW_PRODUCING_KINDS:
            raise InvalidTransitionError(
                f"journal entry {entry_id!r} is a {entry.kind.value} command, "
                "which does not produce a review"
            )
        if entry.project_id != project_id:
            raise InvalidTransitionError(
                f"journal entry {entry_id!r} belongs to project "
                f"{entry.project_id!r}, not {project_id!r}"
            )
