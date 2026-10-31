"""The Runner's one-transaction report of the reviews a run produced.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

A run's reviews have durable effects: each verdict, the ``runner_issued`` ledger
row that tells detection the Runner already owns that file, and the resolution
of the journal entry that issued the run. Done as separate calls, a crash between
them leaves a verdict with an unresolved entry, or a resolved entry with no
verdict. Here they land together or not at all, for any number of reviews,
including none (a failed run, or a run that wrote no review).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence

from amoeba.store import sql_inbox
from amoeba.store._base import isoformat, now
from amoeba.store.evidence_models import VerdictRecord
from amoeba.store.feed import FeedOperations
from amoeba.store.feed_models import DetectionOutcome
from amoeba.store.journal import RESULT_KEY_RUN_ID, JournalOperations
from amoeba.store.journal_models import (
    REVIEW_PRODUCING_KINDS,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
)
from amoeba.store.models import InvalidTransitionError, NodeStatus, StoreIntegrityError
from amoeba.store.runner_models import RunnerReview

#: The outcomes a Runner report may resolve its entry with. A paused run is not
#: finished, so it is not reported.
REPORT_OUTCOMES = frozenset({JournalOutcome.COMPLETED, JournalOutcome.FAILED})


class RunnerReportOperations(JournalOperations, FeedOperations):
    """``record_runner_report``: verdicts, ledger rows and resolution as one commit."""

    def record_runner_report(
        self,
        entry_id: str,
        reviews: Sequence[RunnerReview],
        *,
        outcome: JournalOutcome,
        result: Mapping[str, object],
        complete_node_id: str | None = None,
    ) -> list[VerdictRecord]:
        """Record a run's reviews and resolve its journal entry.

        One transaction, in this order: every check, then for each review in
        order its verdict (with ``record_verdict``'s retry rule) and its
        ``runner_issued`` ledger row carrying the verdict's id and node, then the
        entry resolved by ``issuer`` with ``outcome`` and ``result``. The
        resolution marks the entry as awaiting routing (the store still sets the flag;
        nothing has read it since slice 132).

        With ``complete_node_id`` the node is marked ``done`` in the same
        transaction, after the resolution (a node with an unresolved entry
        cannot be marked done). A crash between a resolution and a separate
        completion would relaunch a run that already finished (slice 132, D4).
        A node that is already ``done`` is left alone. Any other state the
        status rules forbid (a blocked node) raises, as a direct status write
        would.

        A ledger key already present (detection got there first) keeps its
        existing row and inserts nothing; the entry is still resolved. A verdict
        id already recorded returns the existing record, and the ledger row and
        resolution still happen. ``reviews`` may be empty.

        Returns:
            The verdict records, one per review, new or existing, in order.

        Raises:
            ValueError: ``outcome`` is not ``completed`` or ``failed``; a
                review's detection outcome is not ``runner_issued``; ``result``
                lacks ``run_id``; or a verdict failed its checks. Nothing is
                written.
            InvalidTransitionError: The entry does not exist, is already
                resolved, is not a review-producing kind, or belongs to
                another project than a review's ``detection``; or
                ``complete_node_id`` names a node in another project or one
                the status rules refuse to complete. Nothing is written.
            NodeNotFoundError: ``complete_node_id`` names no node. Nothing is
                written.
            StoreIntegrityError: A verdict is recorded in another project.
                Nothing is written.
        """
        if outcome not in REPORT_OUTCOMES:
            raise ValueError(
                "record_runner_report resolves an entry completed or failed, "
                f"not {outcome.value!r}"
            )
        for review in reviews:
            if review.detection.outcome is not DetectionOutcome.RUNNER_ISSUED:
                raise ValueError(
                    f"record_runner_report records a runner_issued review, "
                    f"not {review.detection.outcome.value!r}"
                )
        if RESULT_KEY_RUN_ID not in result:
            raise ValueError(f"result must carry {RESULT_KEY_RUN_ID!r}")

        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            entry = self._require_open_review_entry(entry_id)
            records = [self._record_review(review, entry) for review in reviews]
            self._resolve_entry_within(
                entry_id, outcome, result, JournalResolver.ISSUER
            )
            if complete_node_id is not None:
                self._complete_node_within(complete_node_id, entry)
        return records

    def _complete_node_within(self, node_id: str, entry: JournalEntry) -> None:
        """Mark the node ``done`` inside the report's transaction; ``done`` stays."""
        node = self._require_node(node_id)
        if node.project_id != entry.project_id:
            raise InvalidTransitionError(
                f"node {node_id!r} belongs to project {node.project_id!r}, "
                f"not {entry.project_id!r}"
            )
        if node.status is not NodeStatus.DONE:
            self._write_status(node_id, NodeStatus.DONE, isoformat(now()))

    def _record_review(
        self, review: RunnerReview, entry: JournalEntry
    ) -> VerdictRecord:
        """One review's verdict and ledger row, inside the report's transaction."""
        project_id = review.detection.project_id
        if entry.project_id != project_id:
            raise InvalidTransitionError(
                f"journal entry {entry.id!r} belongs to project "
                f"{entry.project_id!r}, not {project_id!r}"
            )
        record = self._record_verdict_within(review.verdict, project_id)
        if record.project_id != project_id:
            raise StoreIntegrityError(
                f"verdict {record.id!r} is recorded in project "
                f"{record.project_id!r}, not {project_id!r}"
            )
        if self._detection_by_key(review.detection) is None:
            self._insert_detection(
                dataclasses.replace(
                    review.detection, verdict_id=record.id, node_id=record.node_id
                )
            )
        return record

    def _require_open_review_entry(self, entry_id: str) -> JournalEntry:
        """Refuse unless the entry is an unresolved review-producing command."""
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
        return entry
