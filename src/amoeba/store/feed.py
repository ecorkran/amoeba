"""The change feed and the detection ledger: reads and in-process writes.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

Changes are never written here: migration ``006``'s triggers emit them inside
the transaction of whatever write fired them (D8).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from amoeba.store import sql, sql_feed, sql_inbox
from amoeba.store._base import isoformat, now
from amoeba.store._verdict_writer import VerdictWriter
from amoeba.store.evidence_models import VerdictInput, VerdictRecord
from amoeba.store.feed_models import (
    BaselineEntry,
    Change,
    DetectedReview,
    DetectionInput,
    DetectionOutcome,
    ReviewWatch,
)
from amoeba.store.mapping_feed import map_change, map_detected_review, map_watch
from amoeba.store.models import StoreIntegrityError


class FeedOperations(VerdictWriter):
    """Reads of the change log, and the detection ledger's read and write path."""

    def changes(self, project_id: str, *, after: int = 0, limit: int) -> list[Change]:
        """Changes with ``seq > after``, in ``seq`` order, at most ``limit`` of them.

        Raises:
            ValueError: If ``limit`` is less than 1.
        """
        if limit < 1:
            raise ValueError(f"limit must be at least 1, got {limit}")
        rows = self._execute(
            sql_feed.SELECT_CHANGES_AFTER, (project_id, after, limit)
        ).fetchall()
        return [map_change(row) for row in rows]

    def data_version(self) -> int:
        """SQLite's ``PRAGMA data_version`` for this connection.

        It changes only when another connection commits, so a follower that
        sees it unchanged knows nothing new was written. Its own reads never
        change it.
        """
        row = self._execute(sql.PRAGMA_DATA_VERSION, ()).fetchone()
        return int(row[0])

    # ----------------------------------------------------------------------
    # The detection ledger
    # ----------------------------------------------------------------------

    def record_detection(self, detection: DetectionInput) -> DetectedReview:
        """Record one examined file. In-process only.

        Idempotent on ``(project_id, path, digest)``: a key already in the
        ledger returns the existing row unchanged and writes nothing.
        """
        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            existing = self._detection_by_key(detection)
            if existing is not None:
                return existing
            self._insert_detection(detection)
        return self._require_detection(detection)

    def record_detected_verdict(
        self, verdict: VerdictInput, detection: DetectionInput
    ) -> tuple[VerdictRecord, DetectedReview]:
        """Record a detected review's verdict and its ``ingested`` row, atomically.

        104's retry rule applies to the verdict. The ledger row carries the
        verdict's id and node. The hand-edit case — a new ``(path, digest)``
        whose parsed content matches an existing verdict id — records no new
        verdict and one new ``ingested`` row pointing at the existing one.

        Raises:
            ValueError: ``detection.outcome`` is not ``ingested``, or a verdict
                check failed. Nothing is written.
            StoreIntegrityError: The ledger key already exists. Callers skip
                known keys first; this is the UNIQUE constraint's own error.
        """
        if detection.outcome is not DetectionOutcome.INGESTED:
            raise ValueError(
                f"record_detected_verdict records an ingested review, "
                f"not {detection.outcome.value!r}"
            )
        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            record = self._record_verdict_within(verdict, detection.project_id)
            linked = dataclasses.replace(
                detection, verdict_id=record.id, node_id=record.node_id
            )
            self._insert_detection(linked)
        return record, self._require_detection(linked)

    def detection(
        self, project_id: str, path: str, digest: str
    ) -> DetectedReview | None:
        """The ledger row for one ``(path, digest)``, or ``None`` if unseen."""
        row = self._execute(
            sql_feed.SELECT_DETECTION_BY_KEY, (project_id, path, digest)
        ).fetchone()
        return None if row is None else map_detected_review(row)

    def detections(
        self, project_id: str, *, outcome: DetectionOutcome | None = None
    ) -> list[DetectedReview]:
        """The project's ledger, in detection order, optionally one outcome."""
        if outcome is None:
            rows = self._execute(sql_feed.SELECT_DETECTIONS, (project_id,))
        else:
            rows = self._execute(
                sql_feed.SELECT_DETECTIONS_BY_OUTCOME, (project_id, outcome.value)
            )
        return [map_detected_review(row) for row in rows.fetchall()]

    def recorded_since(self, project_id: str, record_id: str) -> bool:
        """Whether a verdict whose id is ``record_id`` now exists in the project.

        True however it got there: detection, ``amoeba ingest review``, or the
        Runner. A verdict recorded under an overridden id
        (``amoeba ingest review --id``) is not seen.
        """
        verdict = self._load_verdict(record_id)
        return verdict is not None and verdict.project_id == project_id

    # ----------------------------------------------------------------------
    # Review watches
    # ----------------------------------------------------------------------

    def watches(self, project_id: str) -> list[ReviewWatch]:
        """The project's registered review directories, active or not."""
        rows = self._execute(sql_feed.SELECT_WATCHES, (project_id,)).fetchall()
        return [map_watch(row) for row in rows]

    def baseline_watch(
        self, project_id: str, reviews_dir: str, entries: Sequence[BaselineEntry]
    ) -> None:
        """Record every file present at registration, then mark the watch baselined.

        One transaction, all or nothing: a partial baseline would let a missed
        file be ingested later as new, out of order. An entry already in the
        ledger is skipped. ``baseline`` rows emit no change.

        Raises:
            StoreIntegrityError: The watch is not registered, or is already
                baselined. Nothing is written.
        """
        timestamp = isoformat(now())
        with self._connection:
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            for entry in entries:
                detection = DetectionInput(
                    project_id=project_id,
                    path=entry.path,
                    digest=entry.digest,
                    outcome=DetectionOutcome.BASELINE,
                )
                if self._detection_by_key(detection) is None:
                    self._insert_detection(detection)
            marked = self._execute(
                sql_feed.MARK_WATCH_BASELINED,
                (timestamp, timestamp, project_id, reviews_dir),
            ).rowcount
            if marked != 1:
                raise StoreIntegrityError(
                    f"watch {reviews_dir!r} in {project_id!r} is not registered "
                    "or is already baselined"
                )

    def _detection_by_key(self, detection: DetectionInput) -> DetectedReview | None:
        return self.detection(detection.project_id, detection.path, detection.digest)

    def _require_detection(self, detection: DetectionInput) -> DetectedReview:
        recorded = self._detection_by_key(detection)
        if recorded is None:
            raise StoreIntegrityError(
                f"detection of {detection.path!r} vanished after insert"
            )
        return recorded

    def _insert_detection(self, detection: DetectionInput) -> None:
        """Insert one ledger row. Never commits: runs in the caller's transaction."""
        self._execute(
            sql_feed.INSERT_DETECTION,
            (
                detection.project_id,
                detection.path,
                detection.digest,
                detection.outcome.value,
                detection.node_id,
                detection.verdict_id,
                detection.record_id,
                detection.detail,
                isoformat(now()),
            ),
        )
