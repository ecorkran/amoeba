"""Every SQL statement and column name for Context Forge links and snapshots.

Sibling of ``sql_feed.py`` under the same rule: a column name or statement for
``cf_links`` or ``cf_snapshots`` appears here and in migration ``008`` and
nowhere else. Every value is a bound parameter, including the ``observed``
outcome the latest-observed query filters on.
"""

from __future__ import annotations

from typing import Final

TABLE_CF_LINKS: Final = "cf_links"
TABLE_CF_SNAPSHOTS: Final = "cf_snapshots"

# --------------------------------------------------------------------------
# cf_links columns — the single definition site
# --------------------------------------------------------------------------

COL_LINK_PROJECT_ID: Final = "project_id"
COL_LINK_CF_PROJECT_ID: Final = "cf_project_id"
COL_LINK_LINKED_AT: Final = "linked_at"

#: Column order for every link SELECT and for row mapping.
LINK_COLUMNS: Final = (
    COL_LINK_PROJECT_ID,
    COL_LINK_CF_PROJECT_ID,
    COL_LINK_LINKED_AT,
)

# --------------------------------------------------------------------------
# cf_snapshots columns — the single definition site
# --------------------------------------------------------------------------

COL_SNAPSHOT_ID: Final = "id"
COL_SNAPSHOT_PROJECT_ID: Final = "project_id"
COL_SNAPSHOT_CF_PROJECT_ID: Final = "cf_project_id"
COL_SNAPSHOT_OUTCOME: Final = "outcome"
COL_SNAPSHOT_STATE: Final = "state"
COL_SNAPSHOT_CHANGED: Final = "changed"
COL_SNAPSHOT_DETAIL: Final = "detail"
COL_SNAPSHOT_CF_UPDATED_AT: Final = "cf_updated_at"
COL_SNAPSHOT_CF_VERSION_LABEL: Final = "cf_version_label"
COL_SNAPSHOT_OBSERVED_AT: Final = "observed_at"

#: Column order for every snapshot SELECT and for row mapping.
SNAPSHOT_COLUMNS: Final = (
    COL_SNAPSHOT_ID,
    COL_SNAPSHOT_PROJECT_ID,
    COL_SNAPSHOT_CF_PROJECT_ID,
    COL_SNAPSHOT_OUTCOME,
    COL_SNAPSHOT_STATE,
    COL_SNAPSHOT_CHANGED,
    COL_SNAPSHOT_DETAIL,
    COL_SNAPSHOT_CF_UPDATED_AT,
    COL_SNAPSHOT_CF_VERSION_LABEL,
    COL_SNAPSHOT_OBSERVED_AT,
)

#: ``id`` is omitted from inserts so SQLite assigns arrival order.
SNAPSHOT_INSERT_COLUMNS: Final = SNAPSHOT_COLUMNS[1:]

#: Index name, so the migration test asserts against a constant.
INDEX_CF_SNAPSHOTS_LINK: Final = "idx_cf_snapshots_link"

#: SQLite's implicit insertion-order column; ``cf_links`` has no other order.
ROWID: Final = "rowid"

_LINK_COLUMN_LIST: Final = ", ".join(LINK_COLUMNS)
_SNAPSHOT_SELECT_LIST: Final = ", ".join(SNAPSHOT_COLUMNS)

#: Linking again is a no-op: the primary key refuses the second row silently.
INSERT_LINK: Final = f"""
INSERT OR IGNORE INTO {TABLE_CF_LINKS} ({_LINK_COLUMN_LIST})
VALUES (?, ?, ?)
"""

SELECT_LINKS: Final = f"""
SELECT {_LINK_COLUMN_LIST}
FROM {TABLE_CF_LINKS}
WHERE {COL_LINK_PROJECT_ID} = ?
ORDER BY {ROWID}
"""

INSERT_SNAPSHOT: Final = f"""
INSERT INTO {TABLE_CF_SNAPSHOTS} ({", ".join(SNAPSHOT_INSERT_COLUMNS)})
VALUES ({", ".join("?" for _ in SNAPSHOT_INSERT_COLUMNS)})
"""

SELECT_SNAPSHOT_BY_ID: Final = f"""
SELECT {_SNAPSHOT_SELECT_LIST}
FROM {TABLE_CF_SNAPSHOTS}
WHERE {COL_SNAPSHOT_ID} = ?
"""

SELECT_SNAPSHOTS: Final = f"""
SELECT {_SNAPSHOT_SELECT_LIST}
FROM {TABLE_CF_SNAPSHOTS}
WHERE {COL_SNAPSHOT_PROJECT_ID} = ?
ORDER BY {COL_SNAPSHOT_ID}
"""

SELECT_LATEST_SNAPSHOT: Final = f"""
SELECT {_SNAPSHOT_SELECT_LIST}
FROM {TABLE_CF_SNAPSHOTS}
WHERE {COL_SNAPSHOT_PROJECT_ID} = ?
  AND {COL_SNAPSHOT_CF_PROJECT_ID} = ?
ORDER BY {COL_SNAPSHOT_ID} DESC
LIMIT 1
"""

#: Parameters: project id, cf project id, the ``observed`` outcome word.
SELECT_LATEST_OBSERVED_SNAPSHOT: Final = f"""
SELECT {_SNAPSHOT_SELECT_LIST}
FROM {TABLE_CF_SNAPSHOTS}
WHERE {COL_SNAPSHOT_PROJECT_ID} = ?
  AND {COL_SNAPSHOT_CF_PROJECT_ID} = ?
  AND {COL_SNAPSHOT_OUTCOME} = ?
ORDER BY {COL_SNAPSHOT_ID} DESC
LIMIT 1
"""
