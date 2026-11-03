"""Migration 014: the nullable reserved_term column on question_records."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from legacy_nodes import LEGACY_INSERT_NODE

from amoeba.store import sql, sql_questions
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    read_schema_version,
)
from amoeba.store.models import NodeStatus

PRIOR_SCHEMA_VERSION = 13
ANSWER_SUBMISSION_SCHEMA_VERSION = 14

PROJECT = "demo"
STAGED_AT = "2026-11-02T00:00:00+00:00"
LEGACY_ENTRY_ID = "e-old"
LEGACY_QUESTION_ID = "q-old"


def _stage_version_thirteen_store(path: Path) -> None:
    """A version-13 store holding one question record."""
    with sqlite3.connect(path) as connection:
        migrate(connection, expected_version=PRIOR_SCHEMA_VERSION)
        connection.execute(
            LEGACY_INSERT_NODE,
            ("n-1", PROJECT, None, "slice", NodeStatus.RUNNABLE.value, "n-1")
            + ("cf-old", None, "old-slice", None)
            + (None,) * 3
            + (STAGED_AT, STAGED_AT),
        )
        connection.execute(
            "INSERT INTO command_journal (id, project_id, node_id, kind, parameters,"
            " issued_at) VALUES (?, ?, ?, ?, ?, ?)",
            (LEGACY_ENTRY_ID, PROJECT, "n-1", "sq_run", "{}", STAGED_AT),
        )
        connection.execute(
            "INSERT INTO question_records (id, project_id, node_id, source_entry_id,"
            " run_id, truncated, state, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                LEGACY_QUESTION_ID,
                PROJECT,
                "n-1",
                LEGACY_ENTRY_ID,
                "run-old",
                0,
                "pending",
                STAGED_AT,
                STAGED_AT,
            ),
        )
        connection.commit()


def test_the_expected_version_includes_the_reserved_term() -> None:
    assert EXPECTED_SCHEMA_VERSION >= ANSWER_SUBMISSION_SCHEMA_VERSION


def test_upgrade_adds_a_null_reserved_term_and_keeps_existing_rows(
    store_file: Path,
) -> None:
    _stage_version_thirteen_store(store_file)
    with sqlite3.connect(store_file) as connection:
        migrate(connection, expected_version=ANSWER_SUBMISSION_SCHEMA_VERSION)
        row = connection.execute(
            f"SELECT {sql_questions.COL_QUESTION_ID},"
            f" {sql_questions.COL_QUESTION_RESERVED_TERM}"
            f" FROM {sql_questions.TABLE_QUESTION_RECORDS}"
        ).fetchone()
        version = read_schema_version(connection)
        nodes = connection.execute(f"SELECT COUNT(*) FROM {sql.TABLE_NODES}").fetchone()

    assert row == (LEGACY_QUESTION_ID, None)
    assert nodes == (1,)
    assert version == ANSWER_SUBMISSION_SCHEMA_VERSION


def test_a_fresh_store_has_the_reserved_term_column_nullable_after_013s_columns(
    store_file: Path,
) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        info = connection.execute(
            f"PRAGMA table_info({sql_questions.TABLE_QUESTION_RECORDS})"
        ).fetchall()

    # Migration 015 adds its columns after it.
    column = info[-1 - len(sql_questions.ANSWERING_COLUMNS)]
    assert column[1] == sql_questions.COL_QUESTION_RESERVED_TERM
    assert column[3] == 0  # notnull flag
    assert column[4] is None  # no default
