"""Migration 007: sessions (slice 241, D6, task 3.2)."""

from __future__ import annotations

import sqlite3

import pytest

from amoeba.store import migrations
from amoeba.store.errors import StoreSchemaError
from amoeba.store.migrations import migrate, migration_files, read_schema_version

SESSION_COLUMNS = {
    "session_id", "member_id", "client", "directory", "started_at", "heartbeat_at",
    "push_confirmed_at",
}  # fmt: skip
ROWS_BEFORE = (
    "SELECT project_id FROM members ORDER BY project_id",
    "SELECT message_id, kind, state FROM messages ORDER BY message_id",
    "SELECT seq, member_id, message_id, event FROM deliveries ORDER BY seq",
)


def _version_six_store_with_mail(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    """A store at version 6 holding members, a request and its delivery."""
    with monkeypatch.context() as patch:
        first_six = migration_files()[:6]
        patch.setattr(migrations, "migration_files", lambda: first_six)
        patch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", 6)
        connection = sqlite3.connect(":memory:", isolation_level=None)
        connection.execute("PRAGMA foreign_keys=ON")
        migrate(connection)
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
        "VALUES ('r1', 'request', 'm1', 'm2', 1, 's', 'b', 'open', 't', 't', 'x')"
    )
    connection.execute(
        "INSERT INTO deliveries (member_id, message_id, event, created_at) "
        "VALUES ('m2', 'r1', 'sent', 't')"
    )
    return connection


def _migrate_to_seven(
    connection: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> int:
    """Run the first seven migrations only, so later ones do not change the check."""
    with monkeypatch.context() as patch:
        first_seven = migration_files()[:7]
        patch.setattr(migrations, "migration_files", lambda: first_seven)
        patch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", 7)
        return migrate(connection)


def _snapshot(connection: sqlite3.Connection) -> list[list[tuple[object, ...]]]:
    return [connection.execute(query).fetchall() for query in ROWS_BEFORE]


def test_a_version_six_store_migrates_to_seven_with_rows_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_six_store_with_mail(monkeypatch)
    before = _snapshot(connection)

    assert _migrate_to_seven(connection, monkeypatch) == 7

    assert read_schema_version(connection) == 7
    assert _snapshot(connection) == before
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_sessions_has_the_design_columns_and_both_indexes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_six_store_with_mail(monkeypatch)
    migrate(connection)

    columns = {row[1] for row in connection.execute("PRAGMA table_info(sessions)")}
    index_names = [row[1] for row in connection.execute("PRAGMA index_list(sessions)")]
    indexed = {
        tuple(row[2] for row in connection.execute(f"PRAGMA index_info({name})"))
        for name in index_names
    }

    assert columns == SESSION_COLUMNS
    assert {("member_id",), ("heartbeat_at",)} <= indexed


def test_a_store_stamped_eight_is_refused_and_left_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_six_store_with_mail(monkeypatch)
    _migrate_to_seven(connection, monkeypatch)
    connection.execute("UPDATE schema_meta SET version = 8")
    before = _snapshot(connection)

    with pytest.raises(StoreSchemaError):
        _migrate_to_seven(connection, monkeypatch)

    assert read_schema_version(connection) == 8
    assert _snapshot(connection) == before
