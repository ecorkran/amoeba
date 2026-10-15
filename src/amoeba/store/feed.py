"""The change feed and the detection ledger: reads and in-process writes.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

Changes are never written here: migration ``006``'s triggers emit them inside
the transaction of whatever write fired them (D8).
"""

from __future__ import annotations

from amoeba.store import sql, sql_feed, sql_inbox
from amoeba.store._base import isoformat, now
from amoeba.store._verdict_writer import VerdictWriter
from amoeba.store.feed_models import (
    Change,
    DetectedReview,
    DetectionInput,
    DetectionOutcome,
)
from amoeba.store.mapping_feed import map_change, map_detected_review
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

    def _detection_by_key(self, detection: DetectionInput) -> DetectedReview | None:
        row = self._execute(
            sql_feed.SELECT_DETECTION_BY_KEY,
            (detection.project_id, detection.path, detection.digest),
        ).fetchone()
        return None if row is None else map_detected_review(row)

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
