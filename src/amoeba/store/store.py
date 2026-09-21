"""The store: lifecycle, and the assembled public class.

This is the only module callers touch. Node operations live in ``nodes`` and
blocked-state operations plus the two Runner queries live in ``blocking``; both
are composed into :class:`Store` here, so the public surface is one object while
each file stays near the ~300-line guideline. Statements come from ``sql``, row
mapping from ``mapping``, and schema setup is delegated to ``migrations`` at
open time.

This library does **not** enforce single-writer. The resident process in slice
102 is what adds that; here the caller owns writer discipline. WAL journal mode
is set at open, giving concurrent readers alongside one writer.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Self

from amoeba.store import paths, sql
from amoeba.store.blocking import BlockingOperations
from amoeba.store.journal import JournalOperations
from amoeba.store.migrations import migrate
from amoeba.store.models import StoreCorruptError, StorePermissionError
from amoeba.store.nodes import NodeOperations

logger = logging.getLogger(__name__)

#: Path sqlite3 understands as "an in-memory database", used by
#: :meth:`Store.open_temporary`.
IN_MEMORY_PATH = Path(":memory:")


class Store(NodeOperations, BlockingOperations, JournalOperations):
    """A project-keyed lifecycle node store backed by one SQLite file.

    Open a store with :meth:`open` or :meth:`open_temporary`, both of which
    support the context-manager form::

        with Store.open(path) as store:
            store.create_node(project_id="demo", kind=NodeKind.SLICE, title="x")

    Every write raises on failure; no method returns a status code a caller can
    ignore.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        path: Path,
        busy_timeout_seconds: float = sql.BUSY_TIMEOUT_SECONDS,
    ) -> None:
        """Wrap an already-open, already-migrated connection.

        Callers use :meth:`open` or :meth:`open_temporary` instead.
        """
        super().__init__(connection, busy_timeout_seconds)
        self._path = path

    @property
    def path(self) -> Path:
        """The store file this instance is backed by."""
        return self._path

    @classmethod
    def open(
        cls,
        path: Path | None = None,
        *,
        project_id: str | None = None,
        busy_timeout_seconds: float = sql.BUSY_TIMEOUT_SECONDS,
    ) -> Self:
        """Open a store, creating and migrating it as needed.

        Args:
            path: The store file. When omitted, the central per-supervisor path
                for ``project_id`` is resolved from ``paths``.
            project_id: Used to resolve the central path when ``path`` is
                omitted. Ignored when ``path`` is given.
            busy_timeout_seconds: How long to wait for a contended lock before
                raising. Defaults to the named configuration constant;
                parameterized so a contention test need not wait the full
                production timeout.

        Returns:
            An open store.

        Raises:
            ValueError: If neither ``path`` nor ``project_id`` is given.
            StorePermissionError: If the path or its parent cannot be created,
                read, or written. There is no fallback to a temporary location
                or an in-memory database.
            StoreCorruptError: If the file is not a readable SQLite database.
            StoreSchemaError: If the store is stamped newer than this code.
        """
        if path is None:
            if project_id is None:
                raise ValueError("open() requires either a path or a project_id")
            path = paths.store_path(project_id)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            # Specific: an unwritable or unreachable parent. Typed so no caller
            # mistakes it for a store that simply has no rows yet.
            logger.exception("cannot create store directory %s", path.parent)
            raise StorePermissionError(
                f"cannot create store directory {path.parent}: {error}"
            ) from error

        connection = cls._connect(path, busy_timeout_seconds)
        cls._migrate_or_close(connection)
        return cls(connection, path, busy_timeout_seconds)

    @classmethod
    def open_temporary(cls) -> Self:
        """Open a throwaway in-memory store, for demos and the walkthrough.

        The store exists only for the lifetime of the connection and is never
        written to the central per-supervisor path.
        """
        connection = cls._connect(IN_MEMORY_PATH)
        cls._migrate_or_close(connection)
        return cls(connection, IN_MEMORY_PATH)

    @staticmethod
    def _migrate_or_close(connection: sqlite3.Connection) -> None:
        """Migrate a fresh connection, closing it if migration fails.

        Shared by both constructors so they give the same failure guarantee:
        a failed open never leaks a connection.
        """
        try:
            migrate(connection)
        except Exception:
            logger.exception("migration failed; closing the connection")
            connection.close()
            raise

    @staticmethod
    def _connect(
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
            raise StorePermissionError(
                f"cannot open store at {path}: {error}"
            ) from error

        try:
            connection.execute(sql.PRAGMA_JOURNAL_MODE)
            connection.execute(sql.PRAGMA_FOREIGN_KEYS_ON)
        except sqlite3.DatabaseError as error:
            connection.close()
            # Specific: a non-SQLite or malformed file fails on first real use.
            logger.exception("cannot configure store at %s", path)
            raise StoreCorruptError(f"cannot read store at {path}: {error}") from error

        return connection

    def close(self) -> None:
        """Close the underlying connection. Safe to call more than once."""
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the connection on normal and exception exit alike."""
        self.close()
