"""Migration 011: ``command_journal.awaits_routing`` and its partial index.

A populated version-10 store upgrades intact, every existing row reads as not
awaiting routing, and the index serves the routing query.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from legacy_nodes import LEGACY_INSERT_NODE

from amoeba.store import Store, sql_journal
from amoeba.store.journal_models import CommandKind, JournalEntry
from amoeba.store.mapping_journal import map_journal_entry
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    read_schema_version,
)
from amoeba.store.models import NodeKind, NodeStatus, UnknownVocabularyValueError

PRIOR_SCHEMA_VERSION = 10
FLAG_SCHEMA_VERSION = 11

PROJECT = "demo"
STAGED_AT = "2026-10-24T00:00:00+00:00"
OLD_ENTRY_IDS = ("j-open", "j-done")


def _stage_version_ten_store(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        migrate(connection, expected_version=PRIOR_SCHEMA_VERSION)
        connection.execute(
            LEGACY_INSERT_NODE,
            ("n-1", PROJECT, None, "slice", NodeStatus.RUNNABLE.value, "n-1")
            + ("cf-old", None, "old-slice", None)
            + (None,) * 3
            + (STAGED_AT, STAGED_AT),
        )
        for entry_id, outcome in zip(OLD_ENTRY_IDS, (None, "completed"), strict=True):
            connection.execute(
                "INSERT INTO command_journal (id, project_id, node_id, kind, "
                "parameters, issued_at, outcome) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    entry_id,
                    PROJECT,
                    "n-1",
                    CommandKind.CF_WRITE.value,
                    json.dumps({}),
                    STAGED_AT,
                    outcome,
                ),
            )
        connection.commit()


def _journal_rows(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
    columns = ", ".join(
        column
        for column in sql_journal.JOURNAL_COLUMNS
        if column != sql_journal.COL_JOURNAL_AWAITS_ROUTING
    )
    return connection.execute(
        f"SELECT {columns} FROM command_journal ORDER BY id"
    ).fetchall()


def test_the_expected_version_is_eleven() -> None:
    assert EXPECTED_SCHEMA_VERSION == FLAG_SCHEMA_VERSION


def test_upgrade_keeps_old_rows_and_reads_them_as_not_awaiting(
    store_file: Path,
) -> None:
    _stage_version_ten_store(store_file)
    with sqlite3.connect(store_file) as connection:
        before = _journal_rows(connection)
        assert migrate(connection) == FLAG_SCHEMA_VERSION
        after = _journal_rows(connection)
        rows = connection.execute(
            f"SELECT {', '.join(sql_journal.JOURNAL_COLUMNS)} "
            "FROM command_journal ORDER BY id"
        ).fetchall()
        version = read_schema_version(connection)

    assert len(before) == len(OLD_ENTRY_IDS)
    assert after == before
    assert version == FLAG_SCHEMA_VERSION
    assert [row[-1] for row in rows] == [None, None]
    assert [map_journal_entry(row).awaits_routing for row in rows] == [False, False]


def test_the_flag_is_the_last_journal_column_and_exists(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        info = connection.execute("PRAGMA table_info(command_journal)").fetchall()
    assert set(sql_journal.JOURNAL_COLUMNS) == {str(row[1]) for row in info}
    assert sql_journal.JOURNAL_COLUMNS[-1] == sql_journal.COL_JOURNAL_AWAITS_ROUTING


def test_the_partial_index_exists_on_the_flagged_rows(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        found = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
            (sql_journal.INDEX_JOURNAL_AWAITS_ROUTING,),
        ).fetchone()
    assert found is not None
    assert "awaits_routing = 1" in found[0]


@pytest.mark.parametrize(("stored", "expected"), [(None, False), (0, False), (1, True)])
def test_the_row_mapping_reads_null_zero_and_one(
    store: Store, stored: int | None, expected: bool
) -> None:
    node = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="s")
    issued = store.journal_issue(
        node.id,
        kind=CommandKind.CF_WRITE,
        parameters={"project": "p", "expected": {}, "checkout": "/w"},
    )
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE command_journal SET awaits_routing = ? WHERE id = ?",
            (stored, issued.id),
        )

    entry = store.journal_entry(issued.id)

    assert isinstance(entry, JournalEntry)
    assert entry.awaits_routing is expected


def test_a_flag_outside_null_zero_one_is_corruption() -> None:
    row = ("e", PROJECT, "n", "cf_write", "{}", STAGED_AT, None, None, None, None, 2)
    with pytest.raises(UnknownVocabularyValueError):
        map_journal_entry(row)
