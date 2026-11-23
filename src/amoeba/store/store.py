"""The store: open (creating and migrating), then short transactions (slice 222, D2).

Writers are short-lived processes and rely on SQLite's busy timeout. There is no
lock file, pid file or read-only mode; a missing store is created.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Final, Self

from amoeba.store import sql, sql_machines, sql_scope
from amoeba.store.errors import (
    LocalStoreClosedError,
    NoActingMachineError,
    StoreError,
    StorePermissionError,
    store_error_for,
)
from amoeba.store.migrations import migrate

if TYPE_CHECKING:
    from amoeba.store.machines import ActingMachine

logger = logging.getLogger(__name__)

#: How long a connection waits on another writer's lock before ``StoreBusyError``.
BUSY_TIMEOUT_SECONDS: Final = 5.0
#: The pause between tries of the WAL switch of a new store.
WAL_RETRY_SECONDS: Final = 0.01


def _enable_wal(connection: sqlite3.Connection, timeout_seconds: float) -> None:
    """Switch the file to WAL, retrying while another connection is mid-switch.

    On a new file this fails at once with SQLITE_BUSY, the busy handler not being
    consulted, when a second connection is switching or migrating it; two sessions
    starting together on a first run hit it. After ``timeout_seconds`` the error is
    raised as it was, and the caller reports ``StoreBusyError``.
    """
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            connection.execute(sql.PRAGMA_JOURNAL_MODE_WAL)
        except sqlite3.OperationalError as error:
            if error.sqlite_errorcode != sqlite3.SQLITE_BUSY:
                raise
            if time.monotonic() >= deadline:
                raise
            time.sleep(WAL_RETRY_SECONDS)
        else:
            return


class Transaction:
    """One open transaction; store functions take it and run statements through it."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        path: Path,
        busy_timeout_seconds: float,
        acting_machine: ActingMachine | None = None,
    ) -> None:
        self._connection = connection
        self._path = path
        self._busy_timeout_seconds = busy_timeout_seconds
        self._acting_machine = acting_machine

    def acting(self, table: str) -> ActingMachine:
        """The store's acting machine, for an insert into ``table``.

        Raises:
            NoActingMachineError: No acting machine is set; there is no default.
        """
        if self._acting_machine is None:
            raise NoActingMachineError(
                f"the store at {self._path} has no acting machine set, so the "
                f"insert into {table} cannot say whose it is"
            )
        return self._acting_machine

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
        self._acting_machine: ActingMachine | None = None
        self._in_call_scope = False

    def act_as(self, machine: ActingMachine) -> None:
        """Make ``machine`` the owner and machine of every record this store inserts."""
        self._acting_machine = machine

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
            _enable_wal(connection, busy_timeout_seconds)
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
        rolls back if the block raises. Inside :meth:`call_scope` it is a savepoint.

        Raises:
            LocalStoreClosedError: The store was set aside for a hub (D4).
        """
        if self._in_call_scope:
            with self._savepoint() as transaction:
                yield transaction
            return
        with self._transaction(sql.BEGIN_IMMEDIATE, check_closed=True) as transaction:
            yield transaction

    @contextmanager
    def read(self) -> Generator[Transaction, None, None]:
        """A read transaction: one consistent view; commits on exit. Inside
        :meth:`call_scope` it is a savepoint."""
        if self._in_call_scope:
            with self._savepoint() as transaction:
                yield transaction
            return
        with self._transaction(sql.BEGIN_DEFERRED, check_closed=False) as transaction:
            yield transaction

    @contextmanager
    def call_scope(self) -> Generator[Transaction, None, None]:
        """One write transaction for a whole hub call (D8).

        Commits on a normal exit and rolls back on an exception. Inside it,
        ``write()`` and ``read()`` are savepoints: released on a normal exit, rolled
        back to on an exception (which propagates), so an operation that raises
        inside its own block undoes only itself.

        Raises:
            RuntimeError: Already inside a call scope (a programming error).
            LocalStoreClosedError: The store was set aside for a hub (D4).
        """
        if self._in_call_scope:
            raise RuntimeError("call_scope cannot be entered inside a call scope")
        with self._transaction(sql.BEGIN_IMMEDIATE, check_closed=True) as transaction:
            self._in_call_scope = True
            try:
                yield transaction
            finally:
                self._in_call_scope = False

    def _new_transaction(self) -> Transaction:
        return Transaction(
            self._connection,
            path=self.path,
            busy_timeout_seconds=self._busy_timeout_seconds,
            acting_machine=self._acting_machine,
        )

    @contextmanager
    def _savepoint(self) -> Generator[Transaction, None, None]:
        transaction = self._new_transaction()
        transaction.execute(sql_scope.SAVEPOINT)
        completed = False
        try:
            yield transaction
            completed = True
        finally:
            if not completed:
                # Undo only this block's statements, keep the enclosing scope open;
                # the failure propagates.
                self._connection.execute(sql_scope.ROLLBACK_TO_SAVEPOINT)
                self._connection.execute(sql_scope.RELEASE_SAVEPOINT)
        transaction.execute(sql_scope.RELEASE_SAVEPOINT)

    @contextmanager
    def _transaction(
        self, begin: str, *, check_closed: bool
    ) -> Generator[Transaction, None, None]:
        transaction = self._new_transaction()
        transaction.execute(begin)
        committed = False
        try:
            if check_closed:
                self._refuse_if_closed(transaction)
            yield transaction
            transaction.execute(sql.COMMIT)
            committed = True
        finally:
            # Roll back on any failure; the failure propagates.
            if not committed and self._connection.in_transaction:
                self._connection.execute(sql.ROLLBACK)

    def _refuse_if_closed(self, transaction: Transaction) -> None:
        """Raise when the store holds the closed mark (D4); the caller rolls back."""
        mark = transaction.execute(sql_machines.SELECT_CLOSED_MARK).fetchone()
        if mark is None:
            return
        raise LocalStoreClosedError(
            f"the local store at {self.path} was set aside for the hub at "
            f"{mark[0]}, so it takes no more writes. Run `amoeba leave` to put it "
            "back, or run the same `amoeba join` again if the join stopped"
        )

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
