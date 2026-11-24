"""Migration 012: member names, ``origin`` and ``checkouts`` (slice 261, D1, D2)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    read_schema_version,
)
from store.schema_11 import OWNER, OldMember, build_schema_11_store, row_counts

MEMBERS = (
    OldMember("m1", wake_command="make go"),
    OldMember("m2"),
    OldMember("m3", wake_command="other"),
    OldMember("m4", removed=True),
)
INSERT_MEMBER = (
    "INSERT INTO members (project_id, program_id, rules_paths, authorize_allow, "
    "authorize_deny, registered_at, updated_at, removed_at, name, origin, owner_id) "
    f"VALUES (?, 'demo', '[]', '[]', '[]', 't', 't', ?, ?, ?, {OWNER})"
)
INSERT_CHECKOUT = (
    "INSERT INTO checkouts (member_id, machine_id, cf_project_id, path, owner_id, "
    "added_at, updated_at) VALUES (?, (SELECT machine_id FROM machines), ?, '/p', ?, "
    "'t', 't')"
)


@pytest.fixture
def schema_11(tmp_path: Path) -> Path:
    path = tmp_path / "old.sqlite3"
    build_schema_11_store(path, MEMBERS)
    return path


@pytest.fixture
def connection(schema_11: Path) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(schema_11, isolation_level=None)) as opened:
        opened.execute("PRAGMA foreign_keys=ON")
        assert migrate(opened) == read_schema_version(opened) == EXPECTED_SCHEMA_VERSION
        yield opened


def _insert_member(
    connection: sqlite3.Connection,
    project_id: str,
    name: str | None,
    *,
    removed: bool = False,
    origin: str | None = None,
) -> None:
    connection.execute(
        INSERT_MEMBER, (project_id, "t" if removed else None, name, origin)
    )


def test_every_row_survives_and_every_existing_member_is_unnamed(
    schema_11: Path, connection: sqlite3.Connection
) -> None:
    after = row_counts(connection)
    with closing(sqlite3.connect(schema_11)) as old:
        before = row_counts(old)

    assert {table: count for table, count in after.items() if table in before} == before
    assert after["checkouts"] == 0
    rows = connection.execute("SELECT name, origin FROM members").fetchall()
    assert len(rows) == len(MEMBERS)
    assert all(tuple(row) == (None, None) for row in rows)
    commands = connection.execute(
        "SELECT wake_command FROM members ORDER BY registered_at"
    ).fetchall()
    assert [row[0] for row in commands] == ["make go", None, "other", None]


def test_a_new_member_with_no_name_is_refused(
    connection: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="name is required"):
        _insert_member(connection, "m9", None)


@pytest.mark.parametrize("second", ["forge", "Forge", "FORGE"])
def test_two_active_members_cannot_share_a_name_in_any_case(
    connection: sqlite3.Connection, second: str
) -> None:
    _insert_member(connection, "n1", "forge")

    with pytest.raises(sqlite3.IntegrityError):
        _insert_member(connection, "n2", second)


def test_a_removed_members_name_can_be_taken(connection: sqlite3.Connection) -> None:
    _insert_member(connection, "n1", "forge", removed=True)

    _insert_member(connection, "n2", "Forge")


def test_two_members_cannot_share_an_origin_unless_one_is_removed(
    connection: sqlite3.Connection,
) -> None:
    _insert_member(connection, "n1", "a", origin="host/org/repo")
    _insert_member(connection, "n2", "b", removed=True, origin="host/org/repo")

    with pytest.raises(sqlite3.IntegrityError):
        _insert_member(connection, "n3", "c", origin="host/org/repo")


def test_any_number_of_members_may_have_no_origin(
    connection: sqlite3.Connection,
) -> None:
    _insert_member(connection, "n1", "a")
    _insert_member(connection, "n2", "b")


def test_a_checkout_is_unique_per_machine_and_context_forge_id(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        "INSERT INTO machines (name, owner_id, created_at) "
        f"VALUES ('local', {OWNER}, 't')"
    )
    _insert_member(connection, "n1", "a")
    owner = connection.execute("SELECT owner_id FROM owners").fetchone()[0]
    connection.execute(INSERT_CHECKOUT, ("n1", "cf-1", owner))

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(INSERT_CHECKOUT, ("n1", "cf-1", owner))
    connection.execute(INSERT_CHECKOUT, ("n1", "cf-2", owner))


def test_a_checkout_with_no_owner_is_refused(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO machines (name, owner_id, created_at) "
        f"VALUES ('local', {OWNER}, 't')"
    )
    _insert_member(connection, "n1", "a")

    with pytest.raises(sqlite3.IntegrityError, match="owner_id is required"):
        connection.execute(INSERT_CHECKOUT, ("n1", "cf-1", None))
