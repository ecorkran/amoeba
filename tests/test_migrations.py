"""Tests for the schema version stamp and the migration runner."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from amoeba.store import sql
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    UNINITIALIZED_SCHEMA_VERSION,
    migrate,
    read_schema_version,
)
from amoeba.store.models import StoreCorruptError, StoreSchemaError

EXPECTED_TABLES = {
    sql.TABLE_SCHEMA_META,
    sql.TABLE_NODES,
    sql.TABLE_BLOCKED_STATES,
}


def _connect(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path)


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def test_unstamped_store_reads_as_uninitialized(store_file: Path) -> None:
    """A database with no schema_meta table is version 0, not an error."""
    with _connect(store_file) as connection:
        assert read_schema_version(connection) == UNINITIALIZED_SCHEMA_VERSION


def test_fresh_store_migrates_to_the_expected_version(store_file: Path) -> None:
    """Migrating a fresh path creates the schema and stamps the version."""
    with _connect(store_file) as connection:
        stamped = migrate(connection)

        assert stamped == EXPECTED_SCHEMA_VERSION
        assert read_schema_version(connection) == EXPECTED_SCHEMA_VERSION
        assert EXPECTED_TABLES <= _table_names(connection)


def test_expected_index_exists(store_file: Path) -> None:
    """The (project_id, status) index covering both Runner queries is created."""
    with _connect(store_file) as connection:
        migrate(connection)

        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = ?",
            (sql.TABLE_NODES,),
        ).fetchall()

        assert "idx_nodes_project_status" in {str(row[0]) for row in rows}


def test_migrating_an_already_migrated_store_is_a_no_op(store_file: Path) -> None:
    """Re-migrating does not re-apply migrations or disturb existing data."""
    with _connect(store_file) as connection:
        migrate(connection)
        connection.execute(
            sql.INSERT_NODE,
            (
                "n1",
                "demo",
                None,
                "slice",
                "runnable",
                "survivor",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "2026-09-17T00:00:00+00:00",
                "2026-09-17T00:00:00+00:00",
            ),
        )
        connection.commit()

        assert migrate(connection) == EXPECTED_SCHEMA_VERSION

        row = connection.execute(sql.SELECT_NODE_BY_ID, ("n1",)).fetchone()
        assert row is not None


def test_store_newer_than_the_code_raises(store_file: Path) -> None:
    """A store stamped newer raises the typed error — never a silent downgrade."""
    with _connect(store_file) as connection:
        migrate(connection)
        connection.execute(
            sql.UPSERT_SCHEMA_VERSION,
            (sql.SCHEMA_META_ROW_ID, EXPECTED_SCHEMA_VERSION + 1),
        )
        connection.commit()

        with pytest.raises(StoreSchemaError, match="newer"):
            migrate(connection)


def test_corrupt_file_raises_on_version_read(store_file: Path) -> None:
    """A file that is not a SQLite database raises rather than being replaced."""
    store_file.write_bytes(b"this is definitely not a sqlite database")

    with _connect(store_file) as connection:
        with pytest.raises(StoreCorruptError):
            read_schema_version(connection)


def test_schema_meta_without_a_version_row_raises(store_file: Path) -> None:
    """A schema_meta table holding no row is corruption, not version 0."""
    with _connect(store_file) as connection:
        migrate(connection)
        connection.execute(f"DELETE FROM {sql.TABLE_SCHEMA_META}")  # noqa: S608
        connection.commit()

        with pytest.raises(StoreCorruptError, match="no version row"):
            read_schema_version(connection)


def test_missing_migration_raises_rather_than_skipping(store_file: Path) -> None:
    """Asking for a version with no migration file raises, leaving the stamp."""
    with _connect(store_file) as connection:
        migrate(connection)
        unreachable_version = EXPECTED_SCHEMA_VERSION + 99

        with pytest.raises(StoreSchemaError, match="missing migrations"):
            migrate(connection, expected_version=unreachable_version)

        assert read_schema_version(connection) == EXPECTED_SCHEMA_VERSION


def test_migration_advances_the_stamp_and_data_survives(store_file: Path) -> None:
    """The N to N+1 proof: open at version 1, migrate, keep the data.

    This is the mechanism slices 102-106 add their real migrations onto, so it
    is proven here before anything depends on it.
    """
    with _connect(store_file) as connection:
        migrate(connection, expected_version=1)
        assert read_schema_version(connection) == 1

        connection.execute(
            sql.INSERT_NODE,
            (
                "n1",
                "demo",
                None,
                "slice",
                "runnable",
                "survivor",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "2026-09-17T00:00:00+00:00",
                "2026-09-17T00:00:00+00:00",
            ),
        )
        connection.commit()

        assert migrate(connection, expected_version=2) == 2
        assert read_schema_version(connection) == 2

        row = connection.execute(sql.SELECT_NODE_BY_ID, ("n1",)).fetchone()
        assert row is not None
        assert row[5] == "survivor"


def test_fresh_store_arrives_at_the_latest_version(store_file: Path) -> None:
    """A store created from scratch runs every migration, not only the first."""
    with _connect(store_file) as connection:
        assert migrate(connection) == EXPECTED_SCHEMA_VERSION
        assert EXPECTED_SCHEMA_VERSION >= 2

        columns = {
            str(row[1])
            for row in connection.execute(f"PRAGMA table_info({sql.TABLE_NODES})")
        }
        assert "note" in columns


def test_failed_migration_leaves_the_stamp_unadvanced(
    store_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A migration that fails rolls back: the stamp does not advance."""
    import amoeba.store.migrations as migrations_module

    with _connect(store_file) as connection:
        migrate(connection)
        starting_version = read_schema_version(connection)

        def _broken_apply(
            connection: sqlite3.Connection, version: int, resource: object
        ) -> None:
            with connection:
                connection.executescript("CREATE TABLE half_applied (id TEXT);")
                raise sqlite3.OperationalError("simulated migration failure")

        monkeypatch.setattr(migrations_module, "_apply_migration", _broken_apply)
        monkeypatch.setattr(
            migrations_module,
            "_migration_files",
            lambda: [(starting_version + 1, object())],
        )

        with pytest.raises(sqlite3.OperationalError):
            migrate(connection, expected_version=starting_version + 1)

        assert read_schema_version(connection) == starting_version
