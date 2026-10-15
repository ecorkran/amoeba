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
