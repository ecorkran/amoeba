"""Migration 013: the question_records table, its indexes and its feed triggers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from legacy_nodes import LEGACY_INSERT_NODE

from amoeba.store import Store, StoreSchemaError, sql, sql_questions
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    read_schema_version,
)
from amoeba.store.models import NodeStatus

PRIOR_SCHEMA_VERSION = 12
QUESTIONS_SCHEMA_VERSION = 13

PROJECT = "demo"
STAGED_AT = "2026-11-01T00:00:00+00:00"


def _stage_version_twelve_store(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        migrate(connection, expected_version=PRIOR_SCHEMA_VERSION)
        connection.execute(
            LEGACY_INSERT_NODE,
            ("n-1", PROJECT, None, "slice", NodeStatus.BLOCKED_ON_HUMAN.value, "n-1")
            + ("cf-old", None, "old-slice", None)
            + (None,) * 3
            + (STAGED_AT, STAGED_AT),
        )
        connection.execute(
            sql.INSERT_BLOCKED_STATE,
            ("b-open", "n-1", "human", "waiting", STAGED_AT, STAGED_AT),
        )
        connection.commit()


def _object_names(connection: sqlite3.Connection, kind: str) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = ?", (kind,)
    ).fetchall()
    return {str(row[0]) for row in rows}


def test_the_expected_version_includes_the_question_records() -> None:
    assert EXPECTED_SCHEMA_VERSION >= QUESTIONS_SCHEMA_VERSION


def test_upgrade_keeps_blocked_states_and_adds_an_empty_table(
    store_file: Path,
) -> None:
    _stage_version_twelve_store(store_file)
    with sqlite3.connect(store_file) as connection:
        before = connection.execute(
            f"SELECT * FROM {sql.TABLE_BLOCKED_STATES}"
        ).fetchall()
        migrate(connection, expected_version=QUESTIONS_SCHEMA_VERSION)
        after = connection.execute(
            f"SELECT * FROM {sql.TABLE_BLOCKED_STATES}"
        ).fetchall()
        count = connection.execute(
            f"SELECT COUNT(*) FROM {sql_questions.TABLE_QUESTION_RECORDS}"
        ).fetchone()
        version = read_schema_version(connection)

    assert len(before) == 1
    assert after == before
    assert count == (0,)
    assert version == QUESTIONS_SCHEMA_VERSION


def test_a_fresh_store_has_the_table_columns_indexes_and_both_triggers(
    store_file: Path,
) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        info = connection.execute(
            f"PRAGMA table_info({sql_questions.TABLE_QUESTION_RECORDS})"
        ).fetchall()
        indexes = _object_names(connection, "index")
        triggers = _object_names(connection, "trigger")
        partial = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = "
            "'idx_question_records_blocked_state'"
        ).fetchone()

    assert [str(row[1]) for row in info] == list(sql_questions.QUESTION_COLUMNS)
    assert {
        "idx_question_records_blocked_state",
        "idx_question_records_project_state",
        "idx_question_records_node",
    } <= indexes
    assert {"changes_question_recorded", "changes_question_state_changed"} <= triggers
    assert "blocked_state_id IS NOT NULL" in partial[0]


def test_read_only_open_of_a_version_twelve_store_raises(store_file: Path) -> None:
    _stage_version_twelve_store(store_file)

    with pytest.raises(StoreSchemaError):
        Store.open_read_only(store_file)

    with sqlite3.connect(store_file) as connection:
        assert read_schema_version(connection) == PRIOR_SCHEMA_VERSION
