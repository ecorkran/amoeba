"""The node INSERT as it was before migration 010, for staging old-version stores.

``sql.INSERT_NODE`` writes every current column, so it cannot stage a store that
has not been migrated to the current version. Tests that build such a store (or
that insert a node with no CF index) use this fifteen-column statement instead.
"""

from __future__ import annotations

from typing import Final

from amoeba.store import sql

_LEGACY_COLUMNS: Final = sql.NODE_COLUMNS[:-1]  # without cf_index

LEGACY_INSERT_NODE: Final = (
    f"INSERT INTO {sql.TABLE_NODES} ({', '.join(_LEGACY_COLUMNS)}) "
    f"VALUES ({', '.join('?' * len(_LEGACY_COLUMNS))})"
)

#: The resolution fill as it was before migration 012, for the same purpose.
LEGACY_FILL_RESOLUTION_SLOT: Final = (
    f"UPDATE {sql.TABLE_BLOCKED_STATES} "
    f"SET {sql.COL_BLOCKED_RESOLVED_BY} = ?, "
    f"{sql.COL_BLOCKED_RESOLUTION_DETAIL} = ?, "
    f"{sql.COL_BLOCKED_RESOLVED_AT} = ?, {sql.COL_BLOCKED_UPDATED_AT} = ? "
    f"WHERE {sql.COL_BLOCKED_NODE_ID} = ? AND {sql.COL_BLOCKED_RESOLVED_AT} IS NULL"
)
