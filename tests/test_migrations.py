"""Tests for the schema version stamp and the migration runner."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from amoeba.store import sql, sql_journal
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
    sql_journal.TABLE_COMMAND_JOURNAL,
}

#: The version that introduced the command journal, and the one before it.
JOURNAL_SCHEMA_VERSION = 3
PRE_JOURNAL_SCHEMA_VERSION = 2


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

    This is the mechanism slices 102-110 add their real migrations onto, so it
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


def _insert_node(connection: sqlite3.Connection, node_id: str, title: str) -> None:
    """Insert a node directly, for staging a store at an older version."""
    connection.execute(
        sql.INSERT_NODE,
        (
            node_id,
            "demo",
            None,
            "slice",
            "blocked_on_human",
            title,
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


def _index_names(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = ?",
        (table,),
    ).fetchall()
    return {str(row[0]) for row in rows}


def test_version_two_store_with_data_upgrades_to_three(store_file: Path) -> None:
    """Migration 003 is the first real schema change: existing data survives it.

    Stages a store exactly as slice 101 code would have left it — at version 2,
    carrying nodes and an open blocked state — then migrates and asserts every
    prior row is still there.
    """
    with _connect(store_file) as connection:
        migrate(connection, expected_version=PRE_JOURNAL_SCHEMA_VERSION)
        _insert_node(connection, "n1", "survivor")
        connection.execute(
            sql.INSERT_BLOCKED_STATE,
            (
                "b1",
                "n1",
                "human",
                "waiting on the PM",
                "2026-09-17T00:00:00+00:00",
                "2026-09-17T00:00:00+00:00",
            ),
        )
        connection.commit()

        assert (
            migrate(connection, expected_version=JOURNAL_SCHEMA_VERSION)
            == JOURNAL_SCHEMA_VERSION
        )
        assert read_schema_version(connection) == JOURNAL_SCHEMA_VERSION

        node_row = connection.execute(sql.SELECT_NODE_BY_ID, ("n1",)).fetchone()
        assert node_row is not None
        assert node_row[5] == "survivor"

        blocked_rows = connection.execute(
            sql.SELECT_BLOCKED_STATES_FOR_NODE, ("n1",)
        ).fetchall()
        assert len(blocked_rows) == 1
        assert blocked_rows[0][3] == "waiting on the PM"


def test_journal_table_and_partial_index_exist_after_migration(
    store_file: Path,
) -> None:
    """The table recovery queries, and the partial index that serves it."""
    with _connect(store_file) as connection:
        migrate(connection)

        assert sql_journal.TABLE_COMMAND_JOURNAL in _table_names(connection)

        indexes = _index_names(connection, sql_journal.TABLE_COMMAND_JOURNAL)
        assert sql_journal.INDEX_JOURNAL_UNRESOLVED in indexes
        assert sql_journal.INDEX_JOURNAL_PROJECT in indexes


def test_unresolved_index_is_partial_on_the_recovery_predicate(
    store_file: Path,
) -> None:
    """The partial index matches the recovery query's shape.

    Asserted against the stored DDL rather than by trusting the filename: an
    index over the same columns without the ``WHERE outcome IS NULL`` clause
    would satisfy a name check while serving the recovery query worse.
    """
    with _connect(store_file) as connection:
        migrate(connection)

        ddl = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
            (sql_journal.INDEX_JOURNAL_UNRESOLVED,),
        ).fetchone()

        assert ddl is not None
        statement = str(ddl[0]).lower()
        assert f"{sql_journal.COL_JOURNAL_OUTCOME} is null" in statement


def test_fresh_store_reaches_version_three_directly(store_file: Path) -> None:
    """The fresh path and the upgrade path land on identical schema."""
    upgraded = store_file.parent / "upgraded.sqlite3"

    with _connect(store_file) as fresh:
        migrate(fresh, expected_version=JOURNAL_SCHEMA_VERSION)
        fresh_tables = _table_names(fresh)
        fresh_journal_columns = {
            str(row[1])
            for row in fresh.execute(
                f"PRAGMA table_info({sql_journal.TABLE_COMMAND_JOURNAL})"
            )
        }

    with _connect(upgraded) as stepwise:
        migrate(stepwise, expected_version=PRE_JOURNAL_SCHEMA_VERSION)
        migrate(stepwise, expected_version=JOURNAL_SCHEMA_VERSION)

        assert read_schema_version(stepwise) == JOURNAL_SCHEMA_VERSION
        assert _table_names(stepwise) == fresh_tables
        assert {
            str(row[1])
            for row in stepwise.execute(
                f"PRAGMA table_info({sql_journal.TABLE_COMMAND_JOURNAL})"
            )
        } == fresh_journal_columns


def test_journal_columns_match_the_single_definition_site(store_file: Path) -> None:
    """The table's columns are exactly the names declared in ``sql_journal``."""
    with _connect(store_file) as connection:
        migrate(connection)

        columns = {
            str(row[1])
            for row in connection.execute(
                f"PRAGMA table_info({sql_journal.TABLE_COMMAND_JOURNAL})"
            )
        }

        assert columns == set(sql_journal.JOURNAL_COLUMNS)


def test_store_stamped_above_three_still_refuses_to_downgrade(
    store_file: Path,
) -> None:
    """The newer-than-code rule holds at the new expected version too."""
    with _connect(store_file) as connection:
        migrate(connection, expected_version=JOURNAL_SCHEMA_VERSION)
        connection.execute(
            sql.UPSERT_SCHEMA_VERSION,
            (sql.SCHEMA_META_ROW_ID, JOURNAL_SCHEMA_VERSION + 1),
        )
        connection.commit()

        with pytest.raises(StoreSchemaError, match="newer"):
            migrate(connection, expected_version=JOURNAL_SCHEMA_VERSION)

        assert read_schema_version(connection) == JOURNAL_SCHEMA_VERSION + 1


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
