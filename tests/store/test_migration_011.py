"""Migration 011: owners, machines, kept results, closed mark (slice 260, D12)."""

from __future__ import annotations

import sqlite3

import pytest

from amoeba.store import migrations
from amoeba.store.migrations import migrate, migration_files, read_schema_version
from store.test_migration_010 import VERSION_NINE_ROWS

#: The twelve tables that hold records (D12).
RECORD_TABLES = (
    "programs", "members", "dependency_pairs", "releases", "questions", "answers",
    "standing_answers", "messages", "deliveries", "message_rejections", "sessions",
    "wakes",
)  # fmt: skip
STANDING_ROW = (
    "INSERT INTO standing_answers (text, reach, program_id, member_id, given_at) "
    "VALUES ('rule', 'all', NULL, NULL, 't')"
)
#: One row in each of the twelve tables, as a schema-10 store holds them.
VERSION_TEN_ROWS = {**VERSION_NINE_ROWS, "standing_answers": (STANDING_ROW,)}
INSERT_WITHOUT_OWNER: dict[str, str] = {
    "programs": "INSERT INTO programs VALUES ('p2', NULL, NULL, 't', 't', NULL)",
    "members": (
        "INSERT INTO members (project_id, program_id, rules_paths, authorize_allow, "
        "authorize_deny, registered_at, updated_at, wake_command) "
        "VALUES ('m9', 'demo', '[]', '[]', '[]', 't', 't', 'w')"
    ),
    "dependency_pairs": (
        "INSERT INTO dependency_pairs VALUES ('demo', 'm2', 'm1', 'from_source', "
        "'t', 't', NULL)"
    ),
    "releases": (
        "INSERT INTO releases (member_id, commit_sha, changed, touched, reported_at) "
        "VALUES ('m1', 'def', '[]', '[]', 't')"
    ),
    "questions": (
        "INSERT INTO questions (run_id, paused_at, member_id, question, checkout, "
        "state, claimed_at, updated_at) "
        "VALUES ('r2', 'p', 'm1', 'q', '/c', 'answered', 't', 't')"
    ),
    "answers": (
        "INSERT INTO answers (run_id, paused_at, answered_by, answer, recorded_at, "
        "via) VALUES ('r2', 'p', 'pm', 'a', 't', 'cli')"
    ),
    "standing_answers": STANDING_ROW,
    "messages": (
        "INSERT INTO messages (message_id, kind, from_member, to_member, depth, "
        "subject, body, state, created_at, state_changed_at, expires_at) "
        "VALUES ('r2', 'request', 'm1', 'm2', 1, 's', 'b', 'open', 't', 't', 't')"
    ),
    "deliveries": (
        "INSERT INTO deliveries (member_id, message_id, event, created_at) "
        "VALUES ('m2', 'r1', 'sent', 't')"
    ),
    "message_rejections": (
        "INSERT INTO message_rejections (member_id, operation, code, detail, "
        "created_at) VALUES ('m1', 'send', 'c', 'd', 't')"
    ),
    "sessions": (
        "INSERT INTO sessions (session_id, member_id, client, directory, started_at, "
        "heartbeat_at, owner_id, machine_id) "
        "VALUES ('s2', 'm1', 'claude', '/c', 't', 't', NULL, NULL)"
    ),
    "wakes": (
        "INSERT INTO wakes (wake_id, member_id, command, started_at, deadline_at) "
        "VALUES ('w2', 'm1', 'c', 't', 't')"
    ),
}


def _migrate_to(
    connection: sqlite3.Connection, version: int, patch: pytest.MonkeyPatch
) -> int:
    with patch.context() as inner:
        first = migration_files()[:version]
        inner.setattr(migrations, "migration_files", lambda: first)
        inner.setattr(migrations, "EXPECTED_SCHEMA_VERSION", version)
        return migrate(connection)


def _count(connection: sqlite3.Connection, table: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0])


def _version_ten_store(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.execute("PRAGMA foreign_keys=ON")
    assert _migrate_to(connection, 10, monkeypatch) == 10
    for statements in VERSION_TEN_ROWS.values():
        for statement in statements:
            connection.execute(statement)
    return connection


@pytest.fixture
def migrated(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    connection = _version_ten_store(monkeypatch)
    assert _migrate_to(connection, 11, monkeypatch) == 11
    return connection


def test_the_fixture_holds_a_row_in_each_of_the_twelve_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_ten_store(monkeypatch)

    assert all(_count(connection, table) for table in RECORD_TABLES)


def test_the_migration_adds_one_owner_and_changes_no_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_ten_store(monkeypatch)
    before = {table: _count(connection, table) for table in RECORD_TABLES}

    assert _migrate_to(connection, 11, monkeypatch) == 11

    assert read_schema_version(connection) == 11
    assert [row[0] for row in connection.execute("SELECT name FROM owners")] == ["pm"]
    assert {table: _count(connection, table) for table in RECORD_TABLES} == before
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("table", RECORD_TABLES)
def test_every_existing_row_belongs_to_the_owner(
    migrated: sqlite3.Connection, table: str
) -> None:
    owner = migrated.execute("SELECT owner_id FROM owners").fetchone()[0]

    owners = {row[0] for row in migrated.execute(f"SELECT owner_id FROM {table}")}

    assert owners == {owner}


def test_no_machine_and_no_closed_mark_is_made(migrated: sqlite3.Connection) -> None:
    assert _count(migrated, "machines") == 0
    assert _count(migrated, "closed_mark") == 0
    assert _count(migrated, "call_results") == 0


def test_existing_sessions_keep_a_null_machine(migrated: sqlite3.Connection) -> None:
    assert migrated.execute("SELECT machine_id FROM sessions").fetchall() == [(None,)]


@pytest.mark.parametrize("table", RECORD_TABLES)
def test_an_insert_with_no_owner_is_refused_naming_the_table(
    migrated: sqlite3.Connection, table: str
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match=f"{table}: "):
        migrated.execute(INSERT_WITHOUT_OWNER[table])


def test_a_session_with_no_machine_is_refused(migrated: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="sessions: machine_id"):
        migrated.execute(
            "INSERT INTO sessions (session_id, member_id, client, directory, "
            "started_at, heartbeat_at, owner_id, machine_id) "
            "VALUES ('s2', 'm1', 'claude', '/c', 't', 't', 1, NULL)"
        )


def test_the_closed_mark_holds_at_most_one_row(migrated: sqlite3.Connection) -> None:
    migrated.execute("INSERT INTO closed_mark VALUES (1, 'hub:1', 't')")

    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute("INSERT INTO closed_mark VALUES (2, 'hub:1', 't')")
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute("INSERT INTO closed_mark VALUES (1, 'hub:2', 't')")
