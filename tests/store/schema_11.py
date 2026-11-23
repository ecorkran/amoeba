"""A schema-11 store, built the way ``test_migration_010`` builds its schema-9 one.

Migrated to 11 with the migration list cut there, then rows inserted by plain SQL,
because the seed helpers insert through the current statements and after migration
012 those cannot make an unnamed member. Shared by the migration, naming and
live-update tests (slice 261).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import pytest

from amoeba.store import migrations
from amoeba.store.migrations import migrate, migration_files

SCHEMA_ELEVEN = 11
OWNER = "(SELECT owner_id FROM owners)"
PROGRAM_ID = "demo"
#: A valid stored time, for the rows that need one.
STAMP = "2026-11-01T00:00:00Z"


@dataclass(frozen=True)
class OldMember:
    """One member as a schema-11 store holds it: no name, a wake command maybe."""

    project_id: str
    wake_command: str | None = None
    removed: bool = False


def _registered_at(position: int) -> str:
    return f"2026-11-01T00:00:{position:02d}Z"


def migrate_to_eleven(connection: sqlite3.Connection) -> None:
    """Bring an empty connection to schema 11 whatever the latest version is."""
    with pytest.MonkeyPatch.context() as patch:
        first = migration_files()[:SCHEMA_ELEVEN]
        patch.setattr(migrations, "migration_files", lambda: first)
        patch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", SCHEMA_ELEVEN)
        assert migrate(connection) == SCHEMA_ELEVEN


def _insert_members(
    connection: sqlite3.Connection, members: Sequence[OldMember]
) -> None:
    for position, member in enumerate(members):
        stamp = _registered_at(position)
        removed_at = stamp if member.removed else None
        connection.execute(
            "INSERT INTO members (project_id, program_id, rules_paths, "
            "authorize_allow, authorize_deny, registered_at, updated_at, removed_at, "
            "wake_command, owner_id) "
            f"VALUES (?, ?, '[]', '[]', '[]', ?, ?, ?, ?, {OWNER})",
            (
                member.project_id,
                PROGRAM_ID,
                stamp,
                stamp,
                removed_at,
                member.wake_command,
            ),
        )


def _insert_pair_and_message(
    connection: sqlite3.Connection, members: Sequence[OldMember]
) -> None:
    active = [member for member in members if not member.removed]
    if len(active) < 2:
        return
    provider, consumer = active[0].project_id, active[1].project_id
    connection.execute(
        "INSERT INTO dependency_pairs (program_id, provider_id, consumer_id, "
        "consumed, registered_at, updated_at, owner_id) "
        f"VALUES (?, ?, ?, 'from_source', ?, ?, {OWNER})",
        (PROGRAM_ID, provider, consumer, STAMP, STAMP),
    )
    connection.execute(
        "INSERT INTO messages (message_id, kind, from_member, to_member, depth, "
        "subject, body, state, created_at, state_changed_at, expires_at, owner_id) "
        "VALUES ('r1', 'request', ?, ?, 1, 's', 'b', 'open', ?, ?, ?, "
        f"{OWNER})",
        (provider, consumer, STAMP, STAMP, "2099-01-01T00:00:00Z"),
    )


def build_schema_11_store(path: Path, members: Sequence[OldMember]) -> None:
    """Write a schema-11 store at ``path`` holding ``members`` in registration order.

    The first two active members are a provider and its consumer, and one open
    message goes from the first to the second.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        migrate_to_eleven(connection)
        connection.execute(
            "INSERT INTO programs (program_id, registered_at, updated_at, owner_id) "
            f"VALUES (?, ?, ?, {OWNER})",
            (PROGRAM_ID, STAMP, STAMP),
        )
        _insert_members(connection, members)
        _insert_pair_and_message(connection, members)


def row_counts(connection: sqlite3.Connection) -> dict[str, int]:
    """The number of rows in every table the connection holds."""
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }
