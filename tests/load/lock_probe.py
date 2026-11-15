"""Asks the database, from a second connection, whether the write lock is held."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


def write_lock_is_held(database: Path) -> bool:
    """True when another connection cannot take the write lock right now."""
    with closing(sqlite3.connect(database, timeout=0, isolation_level=None)) as probe:
        try:
            probe.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            return True
        probe.execute("ROLLBACK")
        return False
