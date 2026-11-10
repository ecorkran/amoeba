"""The store: open (creating and migrating), then short transactions (slice 222, D2).

Writers are short-lived processes and rely on SQLite's busy timeout. There is no
lock file, pid file or read-only mode; a missing store is created.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Final, Self

from amoeba.store import sql
from amoeba.store.errors import (
    StoreError,
    StorePermissionError,
    store_error_for,
)
from amoeba.store.migrations import migrate

logger = logging.getLogger(__name__)

#: How long a connection waits on another writer's lock before ``StoreBusyError``.
BUSY_TIMEOUT_SECONDS: Final = 5.0


class Transaction:
    """One open transaction; store functions take it and run statements through it."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        path: Path,
        busy_timeout_seconds: float,
    ) -> None:
        self._connection = connection
        self._path = path
        self._busy_timeout_seconds = busy_timeout_seconds

    def execute(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> sqlite3.Cursor:
        """Run one statement; a sqlite3 failure becomes its typed ``StoreError``."""
        try:
            return self._connection.execute(statement, tuple(parameters))
        except sqlite3.Error as error:
            logger.exception("store statement failed")
            raise store_error_for(
                error,
                path=self._path,
                busy_timeout_seconds=self._busy_timeout_seconds,
            ) from error


class Store:
    """An open store. Build with :meth:`open`."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        path: Path,
        busy_timeout_seconds: float,
    ) -> None:
        self._connection = connection
        self.path = path
        self._busy_timeout_seconds = busy_timeout_seconds

    @classmethod
    def open(
        cls, path: Path, *, busy_timeout_seconds: float = BUSY_TIMEOUT_SECONDS
    ) -> Self:
        """Create the parent directory and store if missing, and migrate.

        Raises:
            StorePermissionError: The directory or file cannot be created or used.
            StoreCorruptError: The file is not a SQLite database.
            StoreBusyError: Another writer held the lock past the timeout.
            StoreSchemaError: The store is stamped newer than this code.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            logger.exception("cannot create store directory %s", path.parent)
            raise StorePermissionError(
                f"cannot create store directory {path.parent}: {error}"
            ) from error
        try:
            connection = sqlite3.connect(
                path, timeout=busy_timeout_seconds, isolation_level=None
            )
        except sqlite3.Error as error:
            logger.exception("cannot open store at %s", path)
            raise store_error_for(
                error, path=path, busy_timeout_seconds=busy_timeout_seconds
            ) from error
        try:
            connection.execute(sql.PRAGMA_JOURNAL_MODE_WAL)
            connection.execute(sql.PRAGMA_FOREIGN_KEYS_ON)
            migrate(connection)
        except StoreError:
            logger.exception("cannot open store at %s", path)
            connection.close()
            raise
        except sqlite3.Error as error:
            logger.exception("cannot open store at %s", path)
            connection.close()
            raise store_error_for(
                error, path=path, busy_timeout_seconds=busy_timeout_seconds
            ) from error
        return cls(connection, path=path, busy_timeout_seconds=busy_timeout_seconds)

    @contextmanager
    def write(self) -> Generator[Transaction, None, None]:
        """A write transaction holding the lock from its start; commits on exit,
        rolls back if the block raises."""
        with self._transaction(sql.BEGIN_IMMEDIATE) as transaction:
            yield transaction

    @contextmanager
    def read(self) -> Generator[Transaction, None, None]:
        """A read transaction: one consistent view; commits on exit."""
        with self._transaction(sql.BEGIN_DEFERRED) as transaction:
            yield transaction

    @contextmanager
    def _transaction(self, begin: str) -> Generator[Transaction, None, None]:
        transaction = Transaction(
            self._connection,
            path=self.path,
            busy_timeout_seconds=self._busy_timeout_seconds,
        )
        transaction.execute(begin)
        try:
            yield transaction
            transaction.execute(sql.COMMIT)
        except BaseException:
            # Roll back on any failure, then let it propagate.
            if self._connection.in_transaction:
                self._connection.execute(sql.ROLLBACK)
            raise

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
