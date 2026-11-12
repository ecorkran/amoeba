"""Copying a store to a new path and verifying the copy (slice 228, D2 steps 2 and 3).

The old store is only ever read, through a read-only connection: a failure anywhere
leaves it as it was. The copy goes to ``new`` with ``Connection.backup`` (a
consistent snapshot even with writers), every ``answers.resume_log`` under the old
directory is rewritten to the new one (223 D10: that column holds absolute paths and
no other column holds a path under the home), and the copy is then checked against
the original. A failed copy or check deletes ``new`` and raises
``StoreRelocateError``. This module takes both paths as arguments and imports
nothing from ``config``.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Final

from amoeba.store import sql
from amoeba.store.errors import StoreRelocateError
from amoeba.store.migrations import read_schema_version

logger = logging.getLogger(__name__)

#: Files SQLite keeps beside a database in WAL mode.
SIDECAR_SUFFIXES: Final = ("-wal", "-shm")


def _open_read_only(path: Path) -> sqlite3.Connection:
    """A connection that cannot write ``path`` and never creates it."""
    return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)


def _discard(path: Path) -> None:
    """Delete a failed copy with its sidecar files; a missing file is no problem."""
    for candidate in (path, *(Path(f"{path}{suffix}") for suffix in SIDECAR_SUFFIXES)):
        candidate.unlink(missing_ok=True)


def _under(directory: str) -> tuple[str, str, str]:
    """The three parameters of the resume-log match for ``directory``."""
    with_separator = directory.rstrip(os.sep) + os.sep
    return directory, with_separator, with_separator


def _rewrite_resume_logs(path: Path, old_prefix: str, new_prefix: str) -> None:
    with closing(sqlite3.connect(path, isolation_level=None)) as connection:
        connection.execute(sql.BEGIN_IMMEDIATE)
        connection.execute(
            sql.REWRITE_RESUME_LOGS_UNDER,
            (new_prefix, old_prefix, *_under(old_prefix)),
        )
        connection.execute(sql.COMMIT)


def _fail_check(check: str, detail: str) -> StoreRelocateError:
    return StoreRelocateError(f"the copy failed its {check} check: {detail}")


def _scalar(connection: sqlite3.Connection, statement: str, *parameters: str) -> object:
    return connection.execute(statement, parameters).fetchone()[0]


def _table_names(connection: sqlite3.Connection) -> list[str]:
    return [row[0] for row in connection.execute(sql.SELECT_USER_TABLE_NAMES)]


def _check_copy(
    source: sqlite3.Connection, copy: sqlite3.Connection, old_prefix: str
) -> None:
    """Raise ``StoreRelocateError`` naming the first check ``copy`` fails."""
    integrity = [row[0] for row in copy.execute(sql.PRAGMA_INTEGRITY_CHECK)]
    if integrity != [sql.INTEGRITY_CHECK_OK]:
        raise _fail_check("integrity_check", "; ".join(integrity))
    old_version, new_version = read_schema_version(source), read_schema_version(copy)
    if old_version != new_version:
        raise _fail_check(
            "schema version", f"old store {old_version}, copy {new_version}"
        )
    tables = _table_names(source)
    if tables != _table_names(copy):
        raise _fail_check(
            "tables", f"old store has {tables}, copy {_table_names(copy)}"
        )
    for table in tables:
        old_count = _scalar(source, sql.count_rows(table))
        new_count = _scalar(copy, sql.count_rows(table))
        if old_count != new_count:
            raise _fail_check(
                f"row count of {table}", f"old store {old_count}, copy {new_count}"
            )
    old_seq, new_seq = (
        _scalar(connection, sql.SELECT_MAX_ANSWER_SEQ) for connection in (source, copy)
    )
    if old_seq != new_seq:
        raise _fail_check("MAX(answers.seq)", f"old store {old_seq}, copy {new_seq}")
    if _scalar(copy, sql.COUNT_RESUME_LOGS_UNDER, *_under(old_prefix)):
        raise _fail_check("resume_log paths", f"some still start with {old_prefix}")


def _normalized_rows(
    connection: sqlite3.Connection, table: str, old_prefix: str, new_prefix: str
) -> list[str]:
    """Every row of ``table`` as sorted text, each ``resume_log`` under ``old_prefix``
    written as it would be under ``new_prefix``."""
    cursor = connection.execute(sql.select_all_rows(table))
    columns = [column[0] for column in cursor.description]
    old_directory, old_with_separator, _ = _under(old_prefix)
    rows: list[str] = []
    for row in cursor:
        values = list(row)
        for index, column in enumerate(columns):
            value = values[index]
            if column == "resume_log" and isinstance(value, str):
                if value == old_directory or value.startswith(old_with_separator):
                    values[index] = new_prefix + value[len(old_prefix) :]
        rows.append(repr(values))
    return sorted(rows)


def _check_same_content(
    source: sqlite3.Connection,
    other: sqlite3.Connection,
    old_prefix: str,
    new_prefix: str,
) -> None:
    """Raise ``StoreRelocateError`` naming the first table whose rows differ."""
    for table in _table_names(source):
        # ``other`` already holds new paths, so its "rewrite" is the identity.
        if _normalized_rows(source, table, old_prefix, new_prefix) != _normalized_rows(
            other, table, new_prefix, new_prefix
        ):
            raise _fail_check("content", f"rows of {table} differ")


def compare_stores(old: Path, new: Path, old_prefix: str, new_prefix: str) -> None:
    """The checks of ``verify_copy``, plus every row's content, with both files
    opened read-only and neither deleted: for deciding whether two existing stores
    are the same. Paths under ``old_prefix`` in the old store count as the same as
    those under ``new_prefix`` in the new one.

    Raises:
        StoreRelocateError: A check failed, or either file could not be read.
    """
    try:
        with (
            closing(_open_read_only(old)) as source,
            closing(_open_read_only(new)) as other,
        ):
            _check_copy(source, other, old_prefix)
            _check_same_content(source, other, old_prefix, new_prefix)
    except (sqlite3.Error, OSError) as error:
        logger.exception("cannot compare the stores at %s and %s", old, new)
        raise StoreRelocateError(f"cannot compare {old} and {new}: {error}") from error


def summarize_store(path: Path) -> str:
    """Every table's row count and ``MAX(answers.seq)`` of the store at ``path``, as
    one line for a message to a person. Unreadable stores are described, not raised.
    """
    try:
        with closing(_open_read_only(path)) as connection:
            counts = ", ".join(
                f"{table}={_scalar(connection, sql.count_rows(table))}"
                for table in _table_names(connection)
            )
            seq = _scalar(connection, sql.SELECT_MAX_ANSWER_SEQ)
            return f"{counts}, MAX(answers.seq)={seq}"
    except (sqlite3.Error, OSError) as error:
        # A summary is only for the message; an unreadable store is what it reports.
        return f"unreadable ({error})"


def verify_copy(old: Path, new: Path, old_prefix: str) -> None:
    """Check the copy at ``new`` against the store at ``old``.

    Integrity, schema version, every table's row count, ``MAX(answers.seq)``, and no
    ``resume_log`` still under ``old_prefix``. A failure deletes ``new``.

    Raises:
        StoreRelocateError: A check failed, or either file could not be read.
    """
    try:
        with (
            closing(_open_read_only(old)) as source,
            closing(sqlite3.connect(new)) as copy,
        ):
            _check_copy(source, copy, old_prefix)
    except StoreRelocateError:
        logger.exception("the copy of %s at %s did not verify", old, new)
        _discard(new)
        raise
    except (sqlite3.Error, OSError) as error:
        logger.exception("cannot verify the copy of %s at %s", old, new)
        _discard(new)
        raise StoreRelocateError(f"cannot verify the copy at {new}: {error}") from error


def copy_store(
    old: Path,
    new: Path,
    old_prefix: str,
    new_prefix: str,
    *,
    after_backup: Callable[[], None] | None = None,
) -> None:
    """Copy the store at ``old`` to ``new``, rewrite its paths, and verify it.

    ``after_backup`` is called once the backup is complete, before the rewrite: the
    seam for simulating a crash inside the copy. Production passes none. The old
    store is never written.

    Raises:
        StoreRelocateError: The copy or its verification failed; ``new`` is gone.
    """
    try:
        with (
            closing(_open_read_only(old)) as source,
            closing(sqlite3.connect(new)) as target,
        ):
            source.backup(target)
        if after_backup is not None:
            after_backup()
        _rewrite_resume_logs(new, old_prefix, new_prefix)
        verify_copy(old, new, old_prefix)
    except StoreRelocateError:
        raise  # verify_copy already logged it and deleted the copy
    except (sqlite3.Error, OSError) as error:
        logger.exception("cannot copy the store at %s to %s", old, new)
        _discard(new)
        raise StoreRelocateError(f"cannot copy {old} to {new}: {error}") from error
