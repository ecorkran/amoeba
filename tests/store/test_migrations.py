"""Migration discovery and the runner (slice 222, D4)."""

from __future__ import annotations

import sqlite3
from importlib import resources

import pytest

from amoeba.store.errors import StoreSchemaError
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    migration_files,
    read_schema_version,
    split_statements,
)


def _empty_database() -> sqlite3.Connection:
    return sqlite3.connect(":memory:", isolation_level=None)


def test_expected_version_is_the_highest_numbered_file() -> None:
    names = [
        entry.name
        for entry in (resources.files("amoeba.store") / "schema").iterdir()
        if entry.name.endswith(".sql")
    ]

    assert EXPECTED_SCHEMA_VERSION == max(int(name[:3]) for name in names)
    assert [version for version, _ in migration_files()] == list(
        range(1, EXPECTED_SCHEMA_VERSION + 1)
    )


def test_migrating_an_empty_database_stamps_the_version() -> None:
    connection = _empty_database()
    assert read_schema_version(connection) == 0

    assert migrate(connection) == EXPECTED_SCHEMA_VERSION

    assert read_schema_version(connection) == EXPECTED_SCHEMA_VERSION
    assert not connection.in_transaction


def test_migrating_twice_applies_nothing_the_second_time() -> None:
    connection = _empty_database()
    migrate(connection)

    assert migrate(connection) == EXPECTED_SCHEMA_VERSION


def test_a_newer_stamp_raises_and_rolls_back() -> None:
    connection = _empty_database()
    migrate(connection)
    connection.execute("UPDATE schema_meta SET version = 50")

    with pytest.raises(StoreSchemaError):
        migrate(connection)

    assert not connection.in_transaction
    assert read_schema_version(connection) == 50


def test_split_statements_keeps_quoted_semicolons_and_comments() -> None:
    script = (
        "-- one\nCREATE TABLE a (x TEXT DEFAULT ';');\n\n"
        "INSERT INTO a VALUES ('y');\n-- end\n"
    )

    assert split_statements(script) == [
        "-- one\nCREATE TABLE a (x TEXT DEFAULT ';');",
        "INSERT INTO a VALUES ('y');",
    ]


def test_split_statements_refuses_a_dangling_statement() -> None:
    with pytest.raises(StoreSchemaError):
        split_statements("CREATE TABLE a (x TEXT)")


NEW_QUESTION_COLUMNS = (
    "slice_label",
    "source_commit",
    "passages",
    "waiting_detail",
    "evidence",
)
NEW_ANSWER_COLUMNS = ("cited", "resume_detail", "resume_log", "resume_at")


def _version_one_store_with_rows() -> sqlite3.Connection:
    """A store as slice 222 left it: migration 001 only, one question and answer."""
    connection = _empty_database()
    connection.execute("PRAGMA foreign_keys=ON")
    first_version, first_script = migration_files()[0]
    assert first_version == 1
    for statement in split_statements(first_script):
        connection.execute(statement)
    connection.execute(
        "INSERT INTO schema_meta (id, version) VALUES (1, ?)", (first_version,)
    )
    connection.execute("INSERT INTO programs VALUES ('demo', NULL, NULL, 't', 't')")
    connection.execute(
        "INSERT INTO members VALUES ('m1', 'demo', '[]', '[]', '[]', 't', 't')"
    )
    connection.execute(
        "INSERT INTO questions (run_id, paused_at, member_id, question, checkout, "
        "state, claimed_at, updated_at) "
        "VALUES ('r1', 'p1', 'm1', 'why?', '/c', 'answered', 't', 't')"
    )
    connection.execute(
        "INSERT INTO answers (run_id, paused_at, answered_by, answer, recorded_at) "
        "VALUES ('r1', 'p1', 'pm', 'because', 't')"
    )
    return connection


def test_a_version_one_store_migrates_to_two_with_its_rows_intact() -> None:
    connection = _version_one_store_with_rows()
    assert read_schema_version(connection) == 1

    assert migrate(connection) == 2

    assert read_schema_version(connection) == 2
    question = connection.execute(
        f"SELECT question, state, {', '.join(NEW_QUESTION_COLUMNS)} FROM questions"
    ).fetchall()
    assert question == [("why?", "answered", None, None, None, None, None)]
    answer = connection.execute(
        f"SELECT answer, answered_by, {', '.join(NEW_ANSWER_COLUMNS)} FROM answers"
    ).fetchall()
    assert answer == [("because", "pm", None, None, None, None)]
