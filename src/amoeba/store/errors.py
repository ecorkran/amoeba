"""The store's typed errors, so no caller mistakes a failure for an empty store."""

from __future__ import annotations

import sqlite3
from pathlib import Path

#: SQLite primary result codes. ``sqlite_errorcode`` may carry an extended code in
#: the upper bits; the low byte is the primary code.
PRIMARY_CODE_MASK = 0xFF


class StoreError(Exception):
    """Base of every store failure."""


class StoreBusyError(StoreError):
    """The store stayed locked for the whole busy timeout."""


class StorePermissionError(StoreError):
    """The store or its directory cannot be created, read or written."""


class StoreCorruptError(StoreError):
    """The file is not a readable SQLite database."""


class StoreSchemaError(StoreError):
    """The store is stamped newer than this code, or its migrations are unusable."""


class StoreIntegrityError(StoreError):
    """A schema constraint (foreign key, unique, check) refused a write."""


class StoreRowError(StoreError):
    """A stored value is not what its column promises."""


def store_error_for(
    error: sqlite3.Error, *, path: Path, busy_timeout_seconds: float
) -> StoreError:
    """The typed error for a sqlite3 failure on the store at ``path``."""
    code = (getattr(error, "sqlite_errorcode", None) or 0) & PRIMARY_CODE_MASK
    if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
        return StoreBusyError(
            f"store at {path} stayed locked for {busy_timeout_seconds}s: {error}"
        )
    if code in (sqlite3.SQLITE_NOTADB, sqlite3.SQLITE_CORRUPT):
        return StoreCorruptError(f"cannot read store at {path}: {error}")
    if code in (sqlite3.SQLITE_CANTOPEN, sqlite3.SQLITE_PERM, sqlite3.SQLITE_READONLY):
        return StorePermissionError(f"cannot use store at {path}: {error}")
    if code == sqlite3.SQLITE_CONSTRAINT:
        return StoreIntegrityError(f"store constraint refused a write: {error}")
    return StoreError(f"unexpected sqlite error on store at {path}: {error}")
