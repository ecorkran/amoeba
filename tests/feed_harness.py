"""Shared helpers for change-feed tests."""

from __future__ import annotations

import sqlite3

from amoeba.store import Store, sql_feed
from amoeba.store.feed_models import Change
from amoeba.store.mapping_feed import map_change


def raw_changes(store: Store, project_id: str) -> list[Change]:
    """Every change for a project, in ``seq`` order, read on a second connection."""
    columns = ", ".join(sql_feed.CHANGE_COLUMNS)
    with sqlite3.connect(store.path) as connection:
        rows = connection.execute(
            f"SELECT {columns} FROM {sql_feed.TABLE_CHANGES} "
            f"WHERE {sql_feed.COL_CHANGE_PROJECT_ID} = ? "
            f"ORDER BY {sql_feed.COL_CHANGE_SEQ}",
            (project_id,),
        ).fetchall()
    return [map_change(row) for row in rows]
