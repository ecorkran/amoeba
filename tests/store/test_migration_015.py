"""Migration 015: the answering-run columns on question_records (slice 144, D11)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from legacy_nodes import LEGACY_INSERT_NODE

from amoeba.store import sql_questions
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    read_schema_version,
)
from amoeba.store.models import NodeStatus

PRIOR_SCHEMA_VERSION = 14
ANSWERING_RUN_SCHEMA_VERSION = 15

PROJECT = "demo"
STAGED_AT = "2026-11-03T00:00:00+00:00"
LEGACY_QUESTION_ID = "q-old"

INSERT_ENTRY = (
    "INSERT INTO command_journal (id, project_id, node_id, kind, parameters,"
    " issued_at) VALUES (?, ?, ?, ?, ?, ?)"
)
INSERT_QUESTION = (
    "INSERT INTO question_records (id, project_id, node_id, source_entry_id,"
    " run_id, truncated, state, created_at, updated_at, answering_entry_id)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def _stage_version_fourteen_store(path: Path) -> None:
    """A version-14 store holding one question record and a spare journal entry."""
    with sqlite3.connect(path) as connection:
        migrate(connection, expected_version=PRIOR_SCHEMA_VERSION)
        connection.execute(
            LEGACY_INSERT_NODE,
            ("n-1", PROJECT, None, "slice", NodeStatus.RUNNABLE.value, "n-1")
            + ("cf-old", None, "old-slice", None)
            + (None,) * 3
            + (STAGED_AT, STAGED_AT),
        )
        for entry_id in ("e-old", "e-source-2", "e-source-3", "e-answer"):
            connection.execute(
                INSERT_ENTRY, (entry_id, PROJECT, "n-1", "sq_run", "{}", STAGED_AT)
            )
        connection.execute(
            "INSERT INTO question_records (id, project_id, node_id, source_entry_id,"
            " run_id, truncated, state, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (LEGACY_QUESTION_ID, PROJECT, "n-1", "e-old", "r", 0, "pending")
            + (STAGED_AT, STAGED_AT),
        )
        connection.commit()


def _add_question(
    connection: sqlite3.Connection,
    question_id: str,
    source_entry_id: str,
    answering_entry_id: str | None,
) -> None:
    connection.execute(
        INSERT_QUESTION,
        (question_id, PROJECT, "n-1", source_entry_id, "r", 0, "pending")
        + (STAGED_AT, STAGED_AT, answering_entry_id),
    )


def test_the_expected_version_includes_the_answering_columns() -> None:
    assert EXPECTED_SCHEMA_VERSION >= ANSWERING_RUN_SCHEMA_VERSION


def test_upgrade_adds_nine_null_columns_and_keeps_existing_rows(
    store_file: Path,
) -> None:
    _stage_version_fourteen_store(store_file)
    columns = ", ".join(sql_questions.ANSWERING_COLUMNS)
    with sqlite3.connect(store_file) as connection:
        migrate(connection, expected_version=ANSWERING_RUN_SCHEMA_VERSION)
        row = connection.execute(
            f"SELECT {sql_questions.COL_QUESTION_ID}, {columns}"
            f" FROM {sql_questions.TABLE_QUESTION_RECORDS}"
        ).fetchone()
        version = read_schema_version(connection)

    assert len(sql_questions.ANSWERING_COLUMNS) == 9
    assert row == (LEGACY_QUESTION_ID,) + (None,) * 9
    assert version == ANSWERING_RUN_SCHEMA_VERSION


def test_two_records_cannot_share_an_answering_entry(store_file: Path) -> None:
    _stage_version_fourteen_store(store_file)
    with sqlite3.connect(store_file) as connection:
        migrate(connection, expected_version=ANSWERING_RUN_SCHEMA_VERSION)
        _add_question(connection, "q-2", "e-source-2", "e-answer")

        with pytest.raises(sqlite3.IntegrityError):
            _add_question(connection, "q-3", "e-source-3", "e-answer")


def test_any_number_of_records_may_have_no_answering_entry(
    store_file: Path,
) -> None:
    _stage_version_fourteen_store(store_file)
    with sqlite3.connect(store_file) as connection:
        migrate(connection, expected_version=ANSWERING_RUN_SCHEMA_VERSION)
        _add_question(connection, "q-2", "e-source-2", None)
        _add_question(connection, "q-3", "e-source-3", None)
        count = connection.execute(
            f"SELECT COUNT(*) FROM {sql_questions.TABLE_QUESTION_RECORDS}"
            f" WHERE {sql_questions.COL_QUESTION_ANSWERING_ENTRY_ID} IS NULL"
        ).fetchone()

    assert count == (3,)
