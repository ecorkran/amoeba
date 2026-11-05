"""Opening and closing SQLite connections for any store line.

The project store and the program store open the same way: connect with WAL and
foreign keys, migrate their own numbered ``.sql`` package to their own version,
or open read-only and refuse any other version. Each store class passes its
migrations package and expected version; nothing here knows either.

Every failure is mapped to a typed store error, so no caller mistakes an
unreadable file for an empty store, and a failed open never leaks a connection.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from amoeba.store import sql
from amoeba.store.migrations import migrate_package, read_schema_version
from amoeba.store.models import (
    StoreCorruptError,
    StorePermissionError,
    StoreSchemaError,
)

logger = logging.getLogger(__name__)


def open_read_write(
    path: Path,
    *,
    package: str,
    expected_version: int,
    busy_timeout_seconds: float,
) -> sqlite3.Connection:
    """Create the parent directory, connect, and migrate to ``expected_version``.

    Raises:
        StorePermissionError: If the path or its parent cannot be created, read,
            or written. There is no fallback to a temporary location.
        StoreCorruptError: If the file is not a readable SQLite database.
        StoreSchemaError: If the store is stamped newer than ``expected_version``.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        # Specific: an unwritable or unreachable parent. Typed so no caller
        # mistakes it for a store that simply has no rows yet.
        logger.exception("cannot create store directory %s", path.parent)
        raise StorePermissionError(
            f"cannot create store directory {path.parent}: {error}"
        ) from error

    connection = connect(path, busy_timeout_seconds)
    migrate_or_close(connection, package=package, expected_version=expected_version)
    return connection


def open_read_only(
    path: Path, *, expected_version: int, busy_timeout_seconds: float
) -> sqlite3.Connection:
    """Open read-only; never migrate, never create, refuse any other version.

    Raises:
        StorePermissionError: If no store exists at the path, or it cannot be
            read. A missing store is never created.
        StoreCorruptError: If the file is not a readable SQLite database.
        StoreSchemaError: If the stamped version is not ``expected_version``, in
            either direction. The file is left exactly as it was found.
    """
    # Checked before connecting: sqlite3 in mode=ro reports a missing file as an
    # unhelpful "unable to open database file", and the caller needs to know the
    # store does not exist rather than that it is unreadable.
    if not path.exists():
        raise StorePermissionError(f"no store exists at {path}")

    connection = connect_read_only(path, busy_timeout_seconds)
    try:
        version = read_schema_version(connection)
        if version != expected_version:
            raise StoreSchemaError(
                f"store at {path} is at schema version {version}, but this "
                f"code expects {expected_version}; a read-only open "
                "never migrates"
            )
    except Exception:
        logger.exception("read-only open failed; closing the connection")
        connection.close()
        raise

    return connection


def migrate_or_close(
    connection: sqlite3.Connection, *, package: str, expected_version: int
) -> None:
    """Migrate a fresh connection, closing it if migration fails.

    Every opener shares this so they give the same failure guarantee: a failed
    open never leaks a connection.
    """
    try:
        migrate_package(connection, package=package, expected_version=expected_version)
    except Exception:
        logger.exception("migration failed; closing the connection")
        connection.close()
        raise


def connect(
    path: Path, busy_timeout_seconds: float = sql.BUSY_TIMEOUT_SECONDS
) -> sqlite3.Connection:
    """Connect, set WAL and the busy timeout, and verify readability."""
    try:
        connection = sqlite3.connect(
            path, timeout=busy_timeout_seconds, isolation_level="DEFERRED"
        )
    except sqlite3.OperationalError as error:
        # Specific: sqlite3 reports an unopenable path this way. Typed so
        # the resolved path reaches the caller in the message.
        logger.exception("cannot open store at %s", path)
        raise StorePermissionError(f"cannot open store at {path}: {error}") from error

    try:
        connection.execute(sql.PRAGMA_JOURNAL_MODE)
        connection.execute(sql.PRAGMA_FOREIGN_KEYS_ON)
    except sqlite3.DatabaseError as error:
        connection.close()
        # Specific: a non-SQLite or malformed file fails on first real use.
        logger.exception("cannot configure store at %s", path)
        raise StoreCorruptError(f"cannot read store at {path}: {error}") from error

    return connection


def connect_read_only(path: Path, busy_timeout_seconds: float) -> sqlite3.Connection:
    """Connect via ``mode=ro`` and verify the file is readable.

    WAL journal mode is deliberately not set here: that is a write, and a WAL
    store is already readable through a read-only handle — the property
    measured in ``tests/test_read_only_open.py``.
    """
    uri = f"file:{path}?mode=ro"
    try:
        connection = sqlite3.connect(
            uri, uri=True, timeout=busy_timeout_seconds, isolation_level="DEFERRED"
        )
    except sqlite3.OperationalError as error:
        # Specific: sqlite3 reports an unopenable path this way.
        logger.exception("cannot open store read-only at %s", path)
        raise StorePermissionError(
            f"cannot open store read-only at {path}: {error}"
        ) from error

    try:
        connection.execute(sql.PRAGMA_FOREIGN_KEYS_ON)
    except sqlite3.DatabaseError as error:
        connection.close()
        # Specific: a non-SQLite or malformed file fails on first real use.
        logger.exception("cannot read store at %s", path)
        raise StoreCorruptError(f"cannot read store at {path}: {error}") from error

    return connection
