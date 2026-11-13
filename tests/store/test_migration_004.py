"""Migration 004: the door recorded on each answer (slice 226, D11, task 2.1)."""

from __future__ import annotations

import sqlite3

import pytest

from amoeba.store import migrations
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    migration_files,
    read_schema_version,
)

ANSWERS_BEFORE = (
    "SELECT seq, run_id, paused_at, answered_by, answer, recorded_at, "
    "resume_outcome FROM answers ORDER BY seq"
)


def _version_three_store_with_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> sqlite3.Connection:
    """A store at version 3 holding one answerer and one PM answer."""
    with monkeypatch.context() as patch:
        first_three = migration_files()[:3]
        patch.setattr(migrations, "migration_files", lambda: first_three)
        patch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", 3)
        connection = sqlite3.connect(":memory:", isolation_level=None)
        connection.execute("PRAGMA foreign_keys=ON")
        migrate(connection)
    connection.execute("INSERT INTO programs VALUES ('demo', NULL, NULL, 't', 't')")
    connection.execute(
        "INSERT INTO members (project_id, program_id, rules_paths, authorize_allow, "
        "authorize_deny, registered_at, updated_at) "
        "VALUES ('m1', 'demo', '[]', '[]', '[]', 't', 't')"
    )
    connection.execute(
        "INSERT INTO questions (run_id, paused_at, member_id, question, checkout, "
        "state, claimed_at, updated_at) "
        "VALUES ('r1', 'p1', 'm1', 'why?', '/c', 'answered', 't', 't')"
    )
    for answered_by in ("answerer", "pm"):
        connection.execute(
            "INSERT INTO answers (run_id, paused_at, answered_by, answer, "
            "recorded_at, resume_outcome) VALUES ('r1', 'p1', ?, 'text', 't', NULL)",
            (answered_by,),
        )
    return connection


def test_a_version_three_store_gets_the_column_with_every_row_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_three_store_with_answers(monkeypatch)
    before = connection.execute(ANSWERS_BEFORE).fetchall()
    assert read_schema_version(connection) == 3

    assert migrate(connection) == 4

    assert EXPECTED_SCHEMA_VERSION == 4
    assert read_schema_version(connection) == 4
    assert connection.execute(ANSWERS_BEFORE).fetchall() == before
    assert connection.execute("SELECT via FROM answers").fetchall() == [
        (None,),
        (None,),
    ]


def test_a_repeat_run_of_the_runner_changes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_three_store_with_answers(monkeypatch)
    migrate(connection)
    snapshot = connection.execute("SELECT * FROM answers ORDER BY seq").fetchall()

    assert migrate(connection) == 4

    assert connection.execute("SELECT * FROM answers ORDER BY seq").fetchall() == (
        snapshot
    )


def test_a_value_that_is_not_a_door_is_refused_by_the_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_three_store_with_answers(monkeypatch)
    migrate(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE answers SET via = 'carrier-pigeon' WHERE seq = 2")
