"""Every SQL statement and every column name used by this package.

This module is the structural mitigation for choosing raw ``sqlite3`` over an
ORM. ``sqlite3`` returns untyped rows, so a column-name typo in a rarely
exercised query would otherwise be a runtime failure rather than a check-time
one. Centralizing the names here means a typo is a single-definition concern:
the statements and the row-mapping code in ``mapping.py`` reference the same
constants.

It holds statements and names only. It imports neither ``sqlite3`` nor the
dataclasses in ``models.py``. Every statement is parameterized — there is no
f-string or concatenated SQL anywhere in this package.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------
# Connection configuration
# --------------------------------------------------------------------------

#: Seconds to wait for a contended lock before raising. A named constant rather
#: than an inline literal at the ``connect`` call, so tests assert against this
#: name and a change happens in exactly one place.
BUSY_TIMEOUT_SECONDS: Final = 5.0

#: Journal mode set at open. WAL gives concurrent readers alongside one writer,
#: which is the access pattern the architecture's writer model settles on.
JOURNAL_MODE: Final = "WAL"

PRAGMA_JOURNAL_MODE: Final = f"PRAGMA journal_mode = {JOURNAL_MODE}"
PRAGMA_FOREIGN_KEYS_ON: Final = "PRAGMA foreign_keys = ON"

# --------------------------------------------------------------------------
# Table names
# --------------------------------------------------------------------------

TABLE_SCHEMA_META: Final = "schema_meta"
TABLE_NODES: Final = "nodes"
TABLE_BLOCKED_STATES: Final = "blocked_states"

# --------------------------------------------------------------------------
# Column names — the single definition site
# --------------------------------------------------------------------------

# schema_meta
COL_META_ID: Final = "id"
COL_META_VERSION: Final = "version"

#: The schema_meta table holds exactly one row, at this id.
SCHEMA_META_ROW_ID: Final = 1

# nodes
COL_NODE_ID: Final = "id"
COL_NODE_PROJECT_ID: Final = "project_id"
COL_NODE_PARENT_ID: Final = "parent_id"
COL_NODE_KIND: Final = "kind"
COL_NODE_STATUS: Final = "status"
COL_NODE_TITLE: Final = "title"
COL_NODE_CF_PROJECT: Final = "cf_project"
COL_NODE_CF_PHASE: Final = "cf_phase"
COL_NODE_CF_SLICE: Final = "cf_slice"
COL_NODE_CF_ARTIFACT_PATH: Final = "cf_artifact_path"
COL_NODE_SQ_RUN_ID: Final = "sq_run_id"
COL_NODE_SQ_REVIEW_ARTIFACT_PATH: Final = "sq_review_artifact_path"
COL_NODE_SQ_REVIEWED_SHA: Final = "sq_reviewed_sha"
COL_NODE_CREATED_AT: Final = "created_at"
COL_NODE_UPDATED_AT: Final = "updated_at"

# blocked_states
COL_BLOCKED_ID: Final = "id"
COL_BLOCKED_NODE_ID: Final = "node_id"
COL_BLOCKED_KIND: Final = "kind"
COL_BLOCKED_CONTEXT: Final = "context"
COL_BLOCKED_RESOLVED_BY: Final = "resolved_by"
COL_BLOCKED_RESOLUTION_DETAIL: Final = "resolution_detail"
COL_BLOCKED_RESOLVED_AT: Final = "resolved_at"
COL_BLOCKED_CREATED_AT: Final = "created_at"
COL_BLOCKED_UPDATED_AT: Final = "updated_at"

#: Column order used by every node SELECT and by node row mapping. Declared
#: once so the statements and the mapper cannot disagree about position.
NODE_COLUMNS: Final = (
    COL_NODE_ID,
    COL_NODE_PROJECT_ID,
    COL_NODE_PARENT_ID,
    COL_NODE_KIND,
    COL_NODE_STATUS,
    COL_NODE_TITLE,
    COL_NODE_CF_PROJECT,
    COL_NODE_CF_PHASE,
    COL_NODE_CF_SLICE,
    COL_NODE_CF_ARTIFACT_PATH,
    COL_NODE_SQ_RUN_ID,
    COL_NODE_SQ_REVIEW_ARTIFACT_PATH,
    COL_NODE_SQ_REVIEWED_SHA,
    COL_NODE_CREATED_AT,
    COL_NODE_UPDATED_AT,
)

#: Column order used by every blocked-state SELECT and by its row mapping.
BLOCKED_STATE_COLUMNS: Final = (
    COL_BLOCKED_ID,
    COL_BLOCKED_NODE_ID,
    COL_BLOCKED_KIND,
    COL_BLOCKED_CONTEXT,
    COL_BLOCKED_RESOLVED_BY,
    COL_BLOCKED_RESOLUTION_DETAIL,
    COL_BLOCKED_RESOLVED_AT,
    COL_BLOCKED_CREATED_AT,
    COL_BLOCKED_UPDATED_AT,
)


def _columns(prefix: str, columns: tuple[str, ...]) -> str:
    """Render a qualified column list for a SELECT.

    Not string-built SQL in the dangerous sense: the inputs are this module's
    own constants, never caller data. Values always travel as parameters.
    """
    return ", ".join(f"{prefix}.{column}" for column in columns)


_NODE_SELECT_LIST: Final = _columns(TABLE_NODES, NODE_COLUMNS)
_BLOCKED_SELECT_LIST: Final = _columns(TABLE_BLOCKED_STATES, BLOCKED_STATE_COLUMNS)

# --------------------------------------------------------------------------
# Schema version
# --------------------------------------------------------------------------

SELECT_SCHEMA_VERSION: Final = f"""
SELECT {COL_META_VERSION}
FROM {TABLE_SCHEMA_META}
WHERE {COL_META_ID} = ?
"""

UPSERT_SCHEMA_VERSION: Final = f"""
INSERT INTO {TABLE_SCHEMA_META} ({COL_META_ID}, {COL_META_VERSION})
VALUES (?, ?)
ON CONFLICT({COL_META_ID})
DO UPDATE SET {COL_META_VERSION} = excluded.{COL_META_VERSION}
"""

SELECT_TABLE_EXISTS: Final = """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name = ?
"""

# --------------------------------------------------------------------------
# Node writes
# --------------------------------------------------------------------------

INSERT_NODE: Final = f"""
INSERT INTO {TABLE_NODES} (
    {COL_NODE_ID},
    {COL_NODE_PROJECT_ID},
    {COL_NODE_PARENT_ID},
    {COL_NODE_KIND},
    {COL_NODE_STATUS},
    {COL_NODE_TITLE},
    {COL_NODE_CF_PROJECT},
    {COL_NODE_CF_PHASE},
    {COL_NODE_CF_SLICE},
    {COL_NODE_CF_ARTIFACT_PATH},
    {COL_NODE_SQ_RUN_ID},
    {COL_NODE_SQ_REVIEW_ARTIFACT_PATH},
    {COL_NODE_SQ_REVIEWED_SHA},
    {COL_NODE_CREATED_AT},
    {COL_NODE_UPDATED_AT}
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

UPDATE_NODE_STATUS: Final = f"""
UPDATE {TABLE_NODES}
SET {COL_NODE_STATUS} = ?, {COL_NODE_UPDATED_AT} = ?
WHERE {COL_NODE_ID} = ?
"""

UPDATE_NODE_CF_REFERENCE: Final = f"""
UPDATE {TABLE_NODES}
SET {COL_NODE_CF_PROJECT} = ?,
    {COL_NODE_CF_PHASE} = ?,
    {COL_NODE_CF_SLICE} = ?,
    {COL_NODE_CF_ARTIFACT_PATH} = ?,
    {COL_NODE_UPDATED_AT} = ?
WHERE {COL_NODE_ID} = ?
"""

UPDATE_NODE_SQ_REFERENCE: Final = f"""
UPDATE {TABLE_NODES}
SET {COL_NODE_SQ_RUN_ID} = ?,
    {COL_NODE_SQ_REVIEW_ARTIFACT_PATH} = ?,
    {COL_NODE_SQ_REVIEWED_SHA} = ?,
    {COL_NODE_UPDATED_AT} = ?
WHERE {COL_NODE_ID} = ?
"""

# --------------------------------------------------------------------------
# Node reads
# --------------------------------------------------------------------------

SELECT_NODE_BY_ID: Final = f"""
SELECT {_NODE_SELECT_LIST}
FROM {TABLE_NODES}
WHERE {TABLE_NODES}.{COL_NODE_ID} = ?
"""

SELECT_NODES_BY_PROJECT: Final = f"""
SELECT {_NODE_SELECT_LIST}
FROM {TABLE_NODES}
WHERE {TABLE_NODES}.{COL_NODE_PROJECT_ID} = ?
ORDER BY {TABLE_NODES}.{COL_NODE_CREATED_AT}, {TABLE_NODES}.{COL_NODE_ID}
"""

SELECT_CHILD_NODES: Final = f"""
SELECT {_NODE_SELECT_LIST}
FROM {TABLE_NODES}
WHERE {TABLE_NODES}.{COL_NODE_PARENT_ID} = ?
ORDER BY {TABLE_NODES}.{COL_NODE_CREATED_AT}, {TABLE_NODES}.{COL_NODE_ID}
"""

# --------------------------------------------------------------------------
# The two Runner queries
# --------------------------------------------------------------------------

#: What is runnable? Nodes in runnable status for one project. Uses the
#: (project_id, status) index.
SELECT_RUNNABLE_NODES: Final = f"""
SELECT {_NODE_SELECT_LIST}
FROM {TABLE_NODES}
WHERE {TABLE_NODES}.{COL_NODE_PROJECT_ID} = ?
  AND {TABLE_NODES}.{COL_NODE_STATUS} = ?
ORDER BY {TABLE_NODES}.{COL_NODE_CREATED_AT}, {TABLE_NODES}.{COL_NODE_ID}
"""

#: What is blocked, and on whom? Each blocked node with its open blocked-state
#: record, so "on whom" needs no second call. The status placeholders are
#: expanded to match the blocked vocabulary size at call time.
SELECT_BLOCKED_NODES_TEMPLATE: Final = f"""
SELECT {_NODE_SELECT_LIST}, {_BLOCKED_SELECT_LIST}
FROM {TABLE_NODES}
JOIN {TABLE_BLOCKED_STATES}
  ON {TABLE_BLOCKED_STATES}.{COL_BLOCKED_NODE_ID} = {TABLE_NODES}.{COL_NODE_ID}
 AND {TABLE_BLOCKED_STATES}.{COL_BLOCKED_RESOLVED_AT} IS NULL
WHERE {TABLE_NODES}.{COL_NODE_PROJECT_ID} = ?
  AND {TABLE_NODES}.{COL_NODE_STATUS} IN ({{status_placeholders}})
ORDER BY {TABLE_NODES}.{COL_NODE_CREATED_AT}, {TABLE_NODES}.{COL_NODE_ID}
"""


def select_blocked_nodes(status_count: int) -> str:
    """Render the blocked query for ``status_count`` status parameters.

    Only the placeholder count varies; every value still travels as a bound
    parameter. ``status_count`` comes from the size of the blocked vocabulary,
    never from caller input.
    """
    placeholders = ", ".join("?" for _ in range(status_count))
    return SELECT_BLOCKED_NODES_TEMPLATE.format(status_placeholders=placeholders)


# --------------------------------------------------------------------------
# Blocked-state writes
# --------------------------------------------------------------------------

INSERT_BLOCKED_STATE: Final = f"""
INSERT INTO {TABLE_BLOCKED_STATES} (
    {COL_BLOCKED_ID},
    {COL_BLOCKED_NODE_ID},
    {COL_BLOCKED_KIND},
    {COL_BLOCKED_CONTEXT},
    {COL_BLOCKED_RESOLVED_BY},
    {COL_BLOCKED_RESOLUTION_DETAIL},
    {COL_BLOCKED_RESOLVED_AT},
    {COL_BLOCKED_CREATED_AT},
    {COL_BLOCKED_UPDATED_AT}
)
VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?, ?)
"""

FILL_RESOLUTION_SLOT: Final = f"""
UPDATE {TABLE_BLOCKED_STATES}
SET {COL_BLOCKED_RESOLVED_BY} = ?,
    {COL_BLOCKED_RESOLUTION_DETAIL} = ?,
    {COL_BLOCKED_RESOLVED_AT} = ?,
    {COL_BLOCKED_UPDATED_AT} = ?
WHERE {COL_BLOCKED_NODE_ID} = ?
  AND {COL_BLOCKED_RESOLVED_AT} IS NULL
"""

#: A resolution submission targets a blocked state by id, never by node, so a
#: stale reply cannot land on a newer block.
SELECT_BLOCKED_STATE_BY_ID: Final = f"""
SELECT {_BLOCKED_SELECT_LIST}
FROM {TABLE_BLOCKED_STATES}
WHERE {TABLE_BLOCKED_STATES}.{COL_BLOCKED_ID} = ?
"""

SELECT_OPEN_BLOCKED_STATE: Final = f"""
SELECT {_BLOCKED_SELECT_LIST}
FROM {TABLE_BLOCKED_STATES}
WHERE {TABLE_BLOCKED_STATES}.{COL_BLOCKED_NODE_ID} = ?
  AND {TABLE_BLOCKED_STATES}.{COL_BLOCKED_RESOLVED_AT} IS NULL
"""

SELECT_BLOCKED_STATES_FOR_NODE: Final = f"""
SELECT {_BLOCKED_SELECT_LIST}
FROM {TABLE_BLOCKED_STATES}
WHERE {TABLE_BLOCKED_STATES}.{COL_BLOCKED_NODE_ID} = ?
ORDER BY {TABLE_BLOCKED_STATES}.{COL_BLOCKED_CREATED_AT}
"""
