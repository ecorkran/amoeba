"""Migration 010: the ``standing_answers`` table (slice 230, D1)."""

from __future__ import annotations

import sqlite3

import pytest

from amoeba.store import migrations
from amoeba.store.migrations import migrate, migration_files, read_schema_version

STANDING_COLUMNS = {
    "id", "text", "reach", "program_id", "member_id", "given_at", "withdrawn_at",
    "withdraw_reason",
}  # fmt: skip
INSERT_STANDING = (
    "INSERT INTO standing_answers (text, reach, program_id, member_id, given_at, "
    "withdrawn_at, withdraw_reason) VALUES (?, ?, ?, ?, 't', ?, ?)"
)
#: One row in every table a version-9 store has, keyed by table.
VERSION_NINE_ROWS: dict[str, tuple[str, ...]] = {
    "programs": ("INSERT INTO programs VALUES ('demo', NULL, NULL, 't', 't')",),
    "members": tuple(
        "INSERT INTO members (project_id, program_id, rules_paths, authorize_allow, "
        "authorize_deny, registered_at, updated_at, wake_command) "
        f"VALUES ('{member}', 'demo', '[]', '[]', '[]', 't', 't', 'w')"
        for member in ("m1", "m2")
    ),
    "dependency_pairs": (
        "INSERT INTO dependency_pairs VALUES "
        "('demo', 'm1', 'm2', 'from_source', 't', 't')",
    ),
    "releases": (
        "INSERT INTO releases (member_id, commit_sha, changed, touched, reported_at) "
        "VALUES ('m1', 'abc', '[]', '[]', 't')",
    ),
    "questions": (
        "INSERT INTO questions (run_id, paused_at, member_id, question, checkout, "
        "state, claimed_at, updated_at) "
        "VALUES ('r', 'p', 'm1', 'q', '/c', 'answered', 't', 't')",
    ),
    "answers": (
        "INSERT INTO answers (run_id, paused_at, answered_by, answer, recorded_at, "
        "via) VALUES ('r', 'p', 'pm', 'a', 't', 'cli')",
    ),
    "pm_marker": ("UPDATE pm_marker SET last_seen_seq = 1",),
    "messages": (
        "INSERT INTO messages (message_id, kind, from_member, to_member, depth, "
        "subject, body, state, created_at, state_changed_at, expires_at) "
        "VALUES ('r1', 'request', 'm1', 'm2', 1, 's', 'b', 'open', 't', 't', 't')",
    ),
    "deliveries": (
        "INSERT INTO deliveries (member_id, message_id, event, created_at) "
        "VALUES ('m2', 'r1', 'sent', 't')",
    ),
    "message_rejections": (
        "INSERT INTO message_rejections (member_id, operation, code, detail, "
        "created_at) VALUES ('m1', 'send', 'c', 'd', 't')",
    ),
    "sessions": (
        "INSERT INTO sessions VALUES ('s', 'm1', 'claude', '/c', 't', 't', NULL)",
    ),
    "wakes": (
        "INSERT INTO wakes (wake_id, member_id, command, started_at, deadline_at) "
        "VALUES ('w', 'm1', 'c', 't', 't')",
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


def _tables(connection: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def _version_nine_store(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    """A version-9 store with at least one row in every table."""
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.execute("PRAGMA foreign_keys=ON")
    assert _migrate_to(connection, 9, monkeypatch) == 9
    for statements in VERSION_NINE_ROWS.values():
        for statement in statements:
            connection.execute(statement)
    return connection


@pytest.fixture
def migrated(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    connection = _version_nine_store(monkeypatch)
    assert _migrate_to(connection, 10, monkeypatch) == 10
    return connection


def test_a_version_nine_store_migrates_with_every_row_equal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_nine_store(monkeypatch)
    tables = _tables(connection)
    before = {
        table: connection.execute(f"SELECT * FROM {table}").fetchall()
        for table in tables
    }
    assert all(rows for table, rows in before.items() if table != "schema_meta")
    assert set(VERSION_NINE_ROWS) | {"schema_meta"} == set(tables)

    assert _migrate_to(connection, 10, monkeypatch) == 10

    assert read_schema_version(connection) == 10
    after = {
        table: connection.execute(f"SELECT * FROM {table}").fetchall()
        for table in tables
        if table != "schema_meta"
    }
    assert after == {table: before[table] for table in after}
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_standing_answers_is_present_and_empty(migrated: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in migrated.execute("PRAGMA table_info(standing_answers)")
    }

    assert columns == STANDING_COLUMNS
    assert migrated.execute("SELECT COUNT(*) FROM standing_answers").fetchone() == (0,)


@pytest.mark.parametrize(
    "values",
    [
        pytest.param(("   ", "all", None, None, None, None), id="blank text"),
        pytest.param(("r", "all", "demo", None, None, None), id="all with program"),
        pytest.param(("r", "all", None, "m1", None, None), id="all with member"),
        pytest.param(("r", "program", None, None, None, None), id="program, none"),
        pytest.param(("r", "program", "demo", "m1", None, None), id="program+member"),
        pytest.param(("r", "member", None, None, None, None), id="member, none"),
        pytest.param(("r", "all", None, None, "t", None), id="withdrawn, no reason"),
        pytest.param(("r", "all", None, None, None, "why"), id="reason, no time"),
        pytest.param(("r", "everyone", None, None, None, None), id="unknown reach"),
    ],
)
def test_a_violating_row_is_refused(
    migrated: sqlite3.Connection, values: tuple[str | None, ...]
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(INSERT_STANDING, values)


def test_a_valid_row_of_each_reach_is_accepted(migrated: sqlite3.Connection) -> None:
    migrated.execute(INSERT_STANDING, ("r", "all", None, None, None, None))
    migrated.execute(INSERT_STANDING, ("r", "program", "demo", None, None, None))
    migrated.execute(INSERT_STANDING, ("r", "member", None, "m1", "t", "why"))

    assert migrated.execute(
        "SELECT reach FROM standing_answers ORDER BY id"
    ).fetchall() == [("all",), ("program",), ("member",)]


def test_a_reach_to_an_unknown_program_or_member_is_refused(
    migrated: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(INSERT_STANDING, ("r", "program", "nope", None, None, None))
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(INSERT_STANDING, ("r", "member", None, "nope", None, None))
