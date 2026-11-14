"""Migration 005: where a member's rules come from (slice 229, D7, D11, task 1.2)."""

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

MEMBER_BEFORE = (
    "SELECT project_id, program_id, rules_paths, authorize_allow, authorize_deny, "
    "registered_at, updated_at, removed_at FROM members ORDER BY project_id"
)


def _version_four_store_with_a_member(
    monkeypatch: pytest.MonkeyPatch,
) -> sqlite3.Connection:
    """A store at version 4 holding one member with named rules."""
    with monkeypatch.context() as patch:
        first_four = migration_files()[:4]
        patch.setattr(migrations, "migration_files", lambda: first_four)
        patch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", 4)
        connection = sqlite3.connect(":memory:", isolation_level=None)
        connection.execute("PRAGMA foreign_keys=ON")
        migrate(connection)
    connection.execute("INSERT INTO programs VALUES ('demo', NULL, NULL, 't', 't')")
    connection.execute(
        "INSERT INTO members (project_id, program_id, rules_paths, authorize_allow, "
        "authorize_deny, registered_at, updated_at) "
        "VALUES ('m1', 'demo', '[\"CLAUDE.md\"]', '[]', '[]', 't', 't')"
    )
    return connection


def test_a_version_four_member_keeps_its_rules_and_reads_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_four_store_with_a_member(monkeypatch)
    before = connection.execute(MEMBER_BEFORE).fetchall()
    assert read_schema_version(connection) == 4

    assert migrate(connection) == 5

    assert EXPECTED_SCHEMA_VERSION == 5
    assert read_schema_version(connection) == 5
    assert connection.execute(MEMBER_BEFORE).fetchall() == before
    assert connection.execute(
        "SELECT rules_paths, rules_from FROM members"
    ).fetchall() == [('["CLAUDE.md"]', "named")]


def test_a_value_that_is_not_a_rules_source_is_refused_by_the_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_four_store_with_a_member(monkeypatch)
    migrate(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE members SET rules_from = 'guess' WHERE project_id = 'm1'"
        )
