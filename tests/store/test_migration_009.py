"""Migration 009: ``members.wake_command`` and the ``wakes`` table (slice 244, D3)."""

from __future__ import annotations

import sqlite3

import pytest

from amoeba.store import migrations
from amoeba.store.errors import StoreSchemaError
from amoeba.store.migrations import migrate, migration_files, read_schema_version

MEMBER_COLUMNS_008 = (
    "project_id, program_id, rules_paths, authorize_allow, authorize_deny, "
    "registered_at, updated_at, removed_at, rules_from"
)
MESSAGE_COLUMNS = "message_id, kind, from_member, to_member, depth, subject, state"
WAKE_COLUMNS = {
    "wake_id", "member_id", "directory", "command", "started_at", "deadline_at",
    "log_stem", "command_pid", "ended_at", "outcome", "exit_code", "detail",
}  # fmt: skip
INSERT_WAKE = (
    "INSERT INTO wakes (wake_id, member_id, command, started_at, deadline_at, "
    "ended_at, outcome, exit_code) VALUES ('w', 'm1', 'c', 't', 't', ?, ?, ?)"
)


def _migrate_to(
    connection: sqlite3.Connection, version: int, patch: pytest.MonkeyPatch
) -> int:
    with patch.context() as inner:
        first = migration_files()[:version]
        inner.setattr(migrations, "migration_files", lambda: first)
        inner.setattr(migrations, "EXPECTED_SCHEMA_VERSION", version)
        return migrate(connection)


def _version_eight_store(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    """A version-8 store with a program, two members and a request."""
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.execute("PRAGMA foreign_keys=ON")
    assert _migrate_to(connection, 8, monkeypatch) == 8
    connection.execute("INSERT INTO programs VALUES ('demo', NULL, NULL, 't', 't')")
    for member in ("m1", "m2"):
        connection.execute(
            "INSERT INTO members (project_id, program_id, rules_paths, "
            "authorize_allow, authorize_deny, registered_at, updated_at) "
            "VALUES (?, 'demo', '[]', '[]', '[]', 't', 't')",
            (member,),
        )
    connection.execute(
        "INSERT INTO messages (message_id, kind, from_member, to_member, depth, "
        "subject, body, state, created_at, state_changed_at, expires_at) "
        "VALUES ('r1', 'request', 'm1', 'm2', 1, 's', 'b', 'open', 't', 't', 't')"
    )
    return connection


@pytest.fixture
def migrated(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    connection = _version_eight_store(monkeypatch)
    assert _migrate_to(connection, 9, monkeypatch) == 9
    return connection


def test_a_version_eight_store_migrates_with_every_row_equal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_eight_store(monkeypatch)
    members = f"SELECT {MEMBER_COLUMNS_008} FROM members ORDER BY project_id"
    messages = f"SELECT {MESSAGE_COLUMNS} FROM messages"
    before = (
        connection.execute(members).fetchall(),
        connection.execute(messages).fetchall(),
    )

    assert _migrate_to(connection, 9, monkeypatch) == 9

    assert read_schema_version(connection) == 9
    assert (
        connection.execute(members).fetchall(),
        connection.execute(messages).fetchall(),
    ) == before
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_every_member_has_no_wake_command_and_wakes_is_empty(
    migrated: sqlite3.Connection,
) -> None:
    assert migrated.execute("SELECT wake_command FROM members").fetchall() == [
        (None,),
        (None,),
    ]
    assert migrated.execute("SELECT COUNT(*) FROM wakes").fetchone() == (0,)
    columns = {row[1] for row in migrated.execute("PRAGMA table_info(wakes)")}
    assert columns == WAKE_COLUMNS


def test_wakes_are_indexed_by_member_and_by_start(migrated: sqlite3.Connection) -> None:
    indexed = {
        tuple(column[2] for column in migrated.execute(f"PRAGMA index_info({row[1]})"))
        for row in migrated.execute("PRAGMA index_list(wakes)")
    }

    assert {("member_id", "started_at"), ("started_at",)} <= indexed


def test_an_outcome_without_ended_at_is_refused(migrated: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(INSERT_WAKE, (None, "timed_out", None))
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(INSERT_WAKE, ("t", None, None))


def test_an_exit_code_on_a_timeout_is_refused(migrated: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(INSERT_WAKE, ("t", "timed_out", 1))


def test_a_valid_unended_and_a_valid_ended_row_are_accepted(
    migrated: sqlite3.Connection,
) -> None:
    migrated.execute(INSERT_WAKE, (None, None, None))
    migrated.execute("DELETE FROM wakes")
    migrated.execute(INSERT_WAKE, ("t", "exited", 3))

    assert migrated.execute("SELECT outcome, exit_code FROM wakes").fetchall() == [
        ("exited", 3)
    ]


def test_an_outcome_outside_the_list_is_refused(migrated: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(INSERT_WAKE, ("t", "vanished", None))


def test_a_store_stamped_ten_is_refused_and_left_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_eight_store(monkeypatch)
    _migrate_to(connection, 9, monkeypatch)
    connection.execute("UPDATE schema_meta SET version = 10")

    with pytest.raises(StoreSchemaError):
        _migrate_to(connection, 9, monkeypatch)

    assert read_schema_version(connection) == 10
