"""The program store: programs, their members, and how members consume each other.

One SQLite file, ``programs/programs.sqlite3`` in the supervisor directory, with
a schema line of its own (``program_schema``, starting at 1). It is its own class
rather than more mixins on ``Store``: it has none of ``Store``'s tables, so "no
project rows in the program store" is structural rather than a convention.

It reuses the project store's machinery: ``connection.py`` opens and migrates
it, ``StatementRunner`` executes statements with the same typed errors.
``open_read_only`` has ``Store.open_read_only``'s guarantees: it never migrates,
never creates, and cannot write.

The store does not exist until the first program submission; the resident
process creates it (``process/project_stores.py``). Reads come from
``_program_reads``; the one write, ``apply_submission``, from ``_program_writer``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Self

from amoeba.store import connection as connection_module
from amoeba.store import sql
from amoeba.store._program_writer import ProgramWriter
from amoeba.store.migrations import (
    EXPECTED_PROGRAM_SCHEMA_VERSION,
    PROGRAM_MIGRATIONS_PACKAGE,
)


class ProgramStore(ProgramWriter):
    """The program store backed by one SQLite file.

    Open with :meth:`open` (resident process only) or :meth:`open_read_only`
    (everything else), both usable as context managers.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        path: Path,
        busy_timeout_seconds: float = sql.BUSY_TIMEOUT_SECONDS,
    ) -> None:
        """Wrap an already-open connection. Callers use :meth:`open` instead."""
        super().__init__(connection, busy_timeout_seconds)
        self._path = path

    @property
    def path(self) -> Path:
        """The store file this instance is backed by."""
        return self._path

    @classmethod
    def open(
        cls, path: Path, *, busy_timeout_seconds: float = sql.BUSY_TIMEOUT_SECONDS
    ) -> Self:
        """Open the program store, creating and migrating it as needed.

        Raises:
            StorePermissionError: If the path or its parent cannot be created,
                read, or written.
            StoreCorruptError: If the file is not a readable SQLite database.
            StoreSchemaError: If the store is stamped newer than this code.
        """
        connection = connection_module.open_read_write(
            path,
            package=PROGRAM_MIGRATIONS_PACKAGE,
            expected_version=EXPECTED_PROGRAM_SCHEMA_VERSION,
            busy_timeout_seconds=busy_timeout_seconds,
        )
        return cls(connection, path, busy_timeout_seconds)

    @classmethod
    def open_read_only(
        cls, path: Path, *, busy_timeout_seconds: float = sql.BUSY_TIMEOUT_SECONDS
    ) -> Self:
        """Open read-only: never migrates, never creates, cannot write.

        Raises:
            StorePermissionError: If no store exists at the path, or it cannot
                be read. A missing store is never created.
            StoreCorruptError: If the file is not a readable SQLite database.
            StoreSchemaError: If the stamped version is not the expected one.
                The file is left exactly as it was found.
        """
        connection = connection_module.open_read_only(
            path,
            expected_version=EXPECTED_PROGRAM_SCHEMA_VERSION,
            busy_timeout_seconds=busy_timeout_seconds,
        )
        return cls(connection, path, busy_timeout_seconds)

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
