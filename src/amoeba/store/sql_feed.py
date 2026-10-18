"""Every SQL statement and column name used by the change feed and detection.

Sibling of ``sql_evidence.py`` under the same rule: a column name or statement
for ``changes``, ``review_watches``, or ``detected_reviews`` appears here and in
migration ``006`` and nowhere else. Every value is a bound parameter.
"""

from __future__ import annotations

from typing import Final

TABLE_CHANGES: Final = "changes"
TABLE_REVIEW_WATCHES: Final = "review_watches"
TABLE_DETECTED_REVIEWS: Final = "detected_reviews"

# --------------------------------------------------------------------------
# changes columns — the single definition site
# --------------------------------------------------------------------------

COL_CHANGE_SEQ: Final = "seq"
COL_CHANGE_PROJECT_ID: Final = "project_id"
COL_CHANGE_KIND: Final = "kind"
COL_CHANGE_NODE_ID: Final = "node_id"
COL_CHANGE_SUBJECT_ID: Final = "subject_id"
COL_CHANGE_PAYLOAD: Final = "payload"
COL_CHANGE_RECORDED_AT: Final = "recorded_at"

#: Column order for every change SELECT and for row mapping.
CHANGE_COLUMNS: Final = (
    COL_CHANGE_SEQ,
    COL_CHANGE_PROJECT_ID,
    COL_CHANGE_KIND,
    COL_CHANGE_NODE_ID,
    COL_CHANGE_SUBJECT_ID,
    COL_CHANGE_PAYLOAD,
    COL_CHANGE_RECORDED_AT,
)

# --------------------------------------------------------------------------
# review_watches columns — the single definition site
# --------------------------------------------------------------------------

COL_WATCH_PROJECT_ID: Final = "project_id"
COL_WATCH_REVIEWS_DIR: Final = "reviews_dir"
COL_WATCH_ACTIVE: Final = "active"
COL_WATCH_REGISTERED_AT: Final = "registered_at"
COL_WATCH_BASELINED_AT: Final = "baselined_at"
COL_WATCH_UPDATED_AT: Final = "updated_at"

#: Column order for every watch SELECT and for row mapping.
WATCH_COLUMNS: Final = (
    COL_WATCH_PROJECT_ID,
    COL_WATCH_REVIEWS_DIR,
    COL_WATCH_ACTIVE,
    COL_WATCH_REGISTERED_AT,
    COL_WATCH_BASELINED_AT,
    COL_WATCH_UPDATED_AT,
)

# --------------------------------------------------------------------------
# detected_reviews columns — the single definition site
# --------------------------------------------------------------------------

COL_DETECTION_ID: Final = "id"
COL_DETECTION_PROJECT_ID: Final = "project_id"
COL_DETECTION_PATH: Final = "path"
COL_DETECTION_DIGEST: Final = "digest"
COL_DETECTION_OUTCOME: Final = "outcome"
COL_DETECTION_NODE_ID: Final = "node_id"
COL_DETECTION_VERDICT_ID: Final = "verdict_id"
COL_DETECTION_RECORD_ID: Final = "record_id"
COL_DETECTION_DETAIL: Final = "detail"
COL_DETECTION_DETECTED_AT: Final = "detected_at"

#: Column order for every ledger SELECT and for row mapping.
DETECTION_COLUMNS: Final = (
    COL_DETECTION_ID,
    COL_DETECTION_PROJECT_ID,
    COL_DETECTION_PATH,
    COL_DETECTION_DIGEST,
    COL_DETECTION_OUTCOME,
    COL_DETECTION_NODE_ID,
    COL_DETECTION_VERDICT_ID,
    COL_DETECTION_RECORD_ID,
    COL_DETECTION_DETAIL,
    COL_DETECTION_DETECTED_AT,
)

#: Index names, so the migration test asserts against a constant.
INDEX_CHANGES_PROJECT_SEQ: Final = "idx_changes_project_seq"


def _select_list(table: str, columns: tuple[str, ...]) -> str:
    return ", ".join(f"{table}.{column}" for column in columns)


# --------------------------------------------------------------------------
# changes statements
# --------------------------------------------------------------------------

#: One project's changes after a cursor, in seq order, capped by a limit.
SELECT_CHANGES_AFTER: Final = f"""
SELECT {_select_list(TABLE_CHANGES, CHANGE_COLUMNS)}
FROM {TABLE_CHANGES}
WHERE {COL_CHANGE_PROJECT_ID} = ?
  AND {COL_CHANGE_SEQ} > ?
ORDER BY {COL_CHANGE_SEQ}
LIMIT ?
"""

#: The feed head: one project's highest seq, or 0 when it has no changes.
SELECT_CHANGE_HEAD: Final = f"""
SELECT COALESCE(MAX({COL_CHANGE_SEQ}), 0)
FROM {TABLE_CHANGES}
WHERE {COL_CHANGE_PROJECT_ID} = ?
"""

#: A read transaction: every statement until ``ROLLBACK`` sees one snapshot.
BEGIN_DEFERRED: Final = "BEGIN DEFERRED"

#: Ends a read transaction; nothing was written, so nothing is lost.
ROLLBACK: Final = "ROLLBACK"

# --------------------------------------------------------------------------
# detected_reviews statements
# --------------------------------------------------------------------------

#: ``id`` is omitted from inserts so SQLite assigns detection order.
DETECTION_INSERT_COLUMNS: Final = DETECTION_COLUMNS[1:]

INSERT_DETECTION: Final = f"""
INSERT INTO {TABLE_DETECTED_REVIEWS} ({", ".join(DETECTION_INSERT_COLUMNS)})
VALUES ({", ".join("?" for _ in DETECTION_INSERT_COLUMNS)})
"""

_DETECTION_SELECT: Final = f"""
SELECT {_select_list(TABLE_DETECTED_REVIEWS, DETECTION_COLUMNS)}
FROM {TABLE_DETECTED_REVIEWS}
"""

SELECT_DETECTION_BY_KEY: Final = (
    _DETECTION_SELECT
    + f"""WHERE {COL_DETECTION_PROJECT_ID} = ?
  AND {COL_DETECTION_PATH} = ?
  AND {COL_DETECTION_DIGEST} = ?
"""
)

SELECT_DETECTIONS: Final = (
    _DETECTION_SELECT
    + f"""WHERE {COL_DETECTION_PROJECT_ID} = ?
ORDER BY {COL_DETECTION_ID}
"""
)

SELECT_DETECTIONS_BY_OUTCOME: Final = (
    _DETECTION_SELECT
    + f"""WHERE {COL_DETECTION_PROJECT_ID} = ?
  AND {COL_DETECTION_OUTCOME} = ?
ORDER BY {COL_DETECTION_ID}
"""
)

# --------------------------------------------------------------------------
# review_watches statements
# --------------------------------------------------------------------------

#: Register a directory, or change an existing watch's ``active``. A new row
#: starts with ``baselined_at`` NULL; an update never touches it, so
#: reactivating a directory does not re-baseline.
UPSERT_WATCH: Final = f"""
INSERT INTO {TABLE_REVIEW_WATCHES} (
    {COL_WATCH_PROJECT_ID},
    {COL_WATCH_REVIEWS_DIR},
    {COL_WATCH_ACTIVE},
    {COL_WATCH_REGISTERED_AT},
    {COL_WATCH_BASELINED_AT},
    {COL_WATCH_UPDATED_AT}
)
VALUES (?, ?, ?, ?, NULL, ?)
ON CONFLICT ({COL_WATCH_PROJECT_ID}, {COL_WATCH_REVIEWS_DIR}) DO UPDATE
SET {COL_WATCH_ACTIVE} = excluded.{COL_WATCH_ACTIVE},
    {COL_WATCH_UPDATED_AT} = excluded.{COL_WATCH_UPDATED_AT}
"""

SELECT_WATCHES: Final = f"""
SELECT {_select_list(TABLE_REVIEW_WATCHES, WATCH_COLUMNS)}
FROM {TABLE_REVIEW_WATCHES}
WHERE {COL_WATCH_PROJECT_ID} = ?
ORDER BY {COL_WATCH_REGISTERED_AT}, {COL_WATCH_REVIEWS_DIR}
"""

#: Set the baseline once. Matches no row for an unregistered or already
#: baselined watch, which the caller treats as an error.
MARK_WATCH_BASELINED: Final = f"""
UPDATE {TABLE_REVIEW_WATCHES}
SET {COL_WATCH_BASELINED_AT} = ?, {COL_WATCH_UPDATED_AT} = ?
WHERE {COL_WATCH_PROJECT_ID} = ?
  AND {COL_WATCH_REVIEWS_DIR} = ?
  AND {COL_WATCH_BASELINED_AT} IS NULL
"""
