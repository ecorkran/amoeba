"""Migration 006: messages, deliveries, message_rejections (slice 240, D1, 1.2)."""

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
    "SELECT project_id, program_id, rules_paths, rules_from, registered_at "
    "FROM members ORDER BY project_id"
)
MESSAGE_COLUMNS = {
    "message_id", "kind", "from_member", "to_member", "to_program", "parent_id",
    "depth", "subject", "body", "state", "result", "result_commit",
    "result_version", "reason", "accepted_at", "created_at", "state_changed_at",
    "expires_at",
}  # fmt: skip
DELIVERY_COLUMNS = {"seq", "member_id", "message_id", "event", "created_at"}
REJECTION_COLUMNS = {
    "id", "member_id", "operation", "to_ref", "message_id", "parent_id", "code",
    "detail", "created_at",
}  # fmt: skip
INSERT_MESSAGE = (
    "INSERT INTO messages (message_id, kind, from_member, to_member, to_program, "
    "depth, subject, body, state, created_at, state_changed_at, expires_at) "
    "VALUES (?, ?, 'm1', ?, ?, ?, 's', 'b', ?, 't', 't', ?)"
)


def _version_five_store_with_members(
    monkeypatch: pytest.MonkeyPatch,
) -> sqlite3.Connection:
    """A store at version 5 holding a program and two members."""
    with monkeypatch.context() as patch:
        first_five = migration_files()[:5]
        patch.setattr(migrations, "migration_files", lambda: first_five)
        patch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", 5)
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
    return connection


@pytest.fixture
def migrated(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    connection = _version_five_store_with_members(monkeypatch)
    assert read_schema_version(connection) == 5
    migrate(connection)
    return connection


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def test_a_version_five_store_migrates_with_rows_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_five_store_with_members(monkeypatch)
    before = connection.execute(MEMBER_BEFORE).fetchall()

    assert migrate(connection) == 6

    assert EXPECTED_SCHEMA_VERSION == 6
    assert read_schema_version(connection) == 6
    assert connection.execute(MEMBER_BEFORE).fetchall() == before
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_the_three_tables_hold_the_design_columns(
    migrated: sqlite3.Connection,
) -> None:
    assert _columns(migrated, "messages") == MESSAGE_COLUMNS
    assert _columns(migrated, "deliveries") == DELIVERY_COLUMNS
    assert _columns(migrated, "message_rejections") == REJECTION_COLUMNS


def test_the_indexes_exist_including_the_one_on_deliveries_message_id(
    migrated: sqlite3.Connection,
) -> None:
    def indexed(table: str) -> set[tuple[str, ...]]:
        names = [row[1] for row in migrated.execute(f"PRAGMA index_list({table})")]
        return {
            tuple(row[2] for row in migrated.execute(f"PRAGMA index_info({name})"))
            for name in names
        }

    assert {
        ("to_member", "state"),
        ("from_member", "state"),
        ("parent_id",),
        ("state", "expires_at"),
    } <= indexed("messages")
    assert {("member_id", "seq"), ("message_id",)} <= indexed("deliveries")
    assert ("created_at",) in indexed("message_rejections")


def test_a_well_formed_request_and_note_are_accepted(
    migrated: sqlite3.Connection,
) -> None:
    migrated.execute(INSERT_MESSAGE, ("r1", "request", "m2", None, 1, "open", "x"))
    migrated.execute(INSERT_MESSAGE, ("n1", "note", "m2", None, 1, None, None))
    migrated.execute(INSERT_MESSAGE, ("n2", "note", None, "demo", 1, None, None))

    assert migrated.execute("SELECT count(*) FROM messages").fetchone() == (3,)


@pytest.mark.parametrize(
    ("row", "why"),
    [
        (("r", "request", "m2", "demo", 1, "open", "x"), "a request with to_program"),
        (("r", "request", None, None, 1, "open", "x"), "a request with no addressee"),
        (("r", "request", "m2", None, 1, None, "x"), "a request without a state"),
        (("r", "request", "m2", None, 1, "open", None), "a request with no expiry"),
        (("n", "note", None, None, 1, None, None), "a note with no recipient"),
        (("n", "note", "m2", "demo", 1, None, None), "a note with both recipients"),
        (("n", "note", "m2", None, 1, "open", None), "a note with a state"),
        (("r", "request", "m2", None, 0, "open", "x"), "a depth of 0"),
        (("r", "letter", "m2", None, 1, "open", "x"), "a bad kind"),
        (("r", "request", "m2", None, 1, "pending", "x"), "a bad state"),
    ],
)
def test_each_message_check_refuses_a_malformed_row(
    migrated: sqlite3.Connection, row: tuple[object, ...], why: str
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(INSERT_MESSAGE, row)


def test_a_delivery_event_that_is_not_in_the_list_is_refused(
    migrated: sqlite3.Connection,
) -> None:
    migrated.execute(INSERT_MESSAGE, ("r1", "request", "m2", None, 1, "open", "x"))
    migrated.execute(
        "INSERT INTO deliveries (member_id, message_id, event, created_at) "
        "VALUES ('m2', 'r1', 'sent', 't')"
    )

    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(
            "INSERT INTO deliveries (member_id, message_id, event, created_at) "
            "VALUES ('m2', 'r1', 'read', 't')"
        )


def test_a_rejection_code_and_operation_are_free_text(
    migrated: sqlite3.Connection,
) -> None:
    migrated.execute(
        "INSERT INTO message_rejections (member_id, operation, code, detail, "
        "created_at) VALUES ('m1', 'a-later-operation', 'a-later-code', 'd', 't')"
    )

    assert migrated.execute("SELECT count(*) FROM message_rejections").fetchone() == (
        1,
    )
