"""The change feed and the detection ledger: reads and in-process writes.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

Changes are never written here: migration ``006``'s triggers emit them inside
the transaction of whatever write fired them (D8).
"""

from __future__ import annotations

from amoeba.store import sql, sql_feed
from amoeba.store._base import StoreBase
from amoeba.store.feed_models import Change
from amoeba.store.mapping_feed import map_change


class FeedOperations(StoreBase):
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
