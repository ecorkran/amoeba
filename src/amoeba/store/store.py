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

from amoeba.store import connection as connection_module
from amoeba.store import paths, sql
from amoeba.store.answer_submission import AnswerSubmissionOperations
from amoeba.store.answering import AnsweringOperations
from amoeba.store.blocking import BlockingOperations
from amoeba.store.calibration import CalibrationOperations
from amoeba.store.cf_snapshots import CFOperations
from amoeba.store.checks import CheckOperations
from amoeba.store.desired_states import DesiredStateOperations
from amoeba.store.feed import FeedOperations
from amoeba.store.inbox import InboxOperations
from amoeba.store.journal import JournalOperations
from amoeba.store.messages import MessageOperations
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION, MIGRATIONS_PACKAGE
from amoeba.store.nodes import NodeOperations
from amoeba.store.project_escalations import ProjectEscalationOperations
from amoeba.store.questions import QuestionOperations
from amoeba.store.routing_decisions import RoutingDecisionOperations
from amoeba.store.runner_report import RunnerReportOperations
from amoeba.store.verdicts import VerdictOperations

logger = logging.getLogger(__name__)

#: Path sqlite3 understands as "an in-memory database", used by
#: :meth:`Store.open_temporary`.
IN_MEMORY_PATH = Path(":memory:")


class Store(
    # First: they extend JournalOperations, FeedOperations and
    # AnswerSubmissionOperations, and a subclass must precede its bases in the
    # method resolution order.
    RunnerReportOperations,
    AnsweringOperations,
    NodeOperations,
    BlockingOperations,
    JournalOperations,
    MessageOperations,
    DesiredStateOperations,
    ProjectEscalationOperations,
    RoutingDecisionOperations,
    AnswerSubmissionOperations,
    QuestionOperations,
    InboxOperations,
    VerdictOperations,
    CheckOperations,
    CalibrationOperations,
    FeedOperations,
    CFOperations,
):
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

        connection = connection_module.open_read_write(
            path,
            package=MIGRATIONS_PACKAGE,
            expected_version=EXPECTED_SCHEMA_VERSION,
            busy_timeout_seconds=busy_timeout_seconds,
        )
        return cls(connection, path, busy_timeout_seconds)

    @classmethod
    def open_read_only(
        cls,
        path: Path | None = None,
        *,
        project_id: str | None = None,
        busy_timeout_seconds: float = sql.BUSY_TIMEOUT_SECONDS,
    ) -> Self:
        """Open a store read-only, for every out-of-process consumer.

        This is what inspection uses. The handle is genuinely read-only —
        SQLite ``mode=ro``, verified against this project's Python and SQLite
        build in ``tests/test_read_only_open.py`` — so a write attempted
        through it raises rather than succeeding silently.

        It **never migrates**. A store at any version other than the one this
        code expects raises :class:`StoreSchemaError`, in both directions:
        migrating would be a write, and reading a newer store risks
        misinterpreting columns this code does not know about.

        Args:
            path: The store file. When omitted, the central per-supervisor path
                for ``project_id`` is resolved from ``paths``.
            project_id: Used to resolve the central path when ``path`` is
                omitted. Ignored when ``path`` is given.
            busy_timeout_seconds: How long to wait for a contended lock before
                raising.

        Returns:
            An open read-only store.

        Raises:
            ValueError: If neither ``path`` nor ``project_id`` is given.
            StorePermissionError: If no store exists at the path, or it cannot
                be read. A missing store is never created.
            StoreCorruptError: If the file is not a readable SQLite database.
            StoreSchemaError: If the store's schema version is not the expected
                one. The file is left exactly as it was found.
        """
        if path is None:
            if project_id is None:
                raise ValueError(
                    "open_read_only() requires either a path or a project_id"
                )
            path = paths.store_path(project_id)

        connection = connection_module.open_read_only(
            path,
            expected_version=EXPECTED_SCHEMA_VERSION,
            busy_timeout_seconds=busy_timeout_seconds,
        )
        return cls(connection, path, busy_timeout_seconds)

    @classmethod
    def open_temporary(cls) -> Self:
        """Open a throwaway in-memory store, for demos and the walkthrough.

        The store exists only for the lifetime of the connection and is never
        written to the central per-supervisor path.
        """
        connection = connection_module.connect(IN_MEMORY_PATH)
        connection_module.migrate_or_close(
            connection,
            package=MIGRATIONS_PACKAGE,
            expected_version=EXPECTED_SCHEMA_VERSION,
        )
        return cls(connection, IN_MEMORY_PATH)

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
