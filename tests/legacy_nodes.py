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
