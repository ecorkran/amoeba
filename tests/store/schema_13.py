"""A schema-13 store holding a machine and session rows (slice 263).

Modeled on ``schema_12``: migrated to 13 with the migration list cut there, then rows
inserted by plain SQL, because the store functions insert through the current
statements and after migration 014 those need the two versions. Shared by the
migration test and the update script's test.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Final

import pytest

from amoeba.store import migrations
from amoeba.store.migrations import migrate, migration_files

SCHEMA_THIRTEEN: Final = 13
OWNER: Final = "(SELECT owner_id FROM owners)"
PROGRAM_ID: Final = "demo"
MEMBER_ID: Final = "m1"
MACHINE_NAME: Final = "local"
STAMP: Final = "2026-11-01T00:00:00Z"
#: Rows held by the store ``build_schema_13_store`` writes.
SESSION_COUNT: Final = 2


def migrate_to_thirteen(connection: sqlite3.Connection) -> None:
    """Bring an empty connection to schema 13 whatever the latest version is."""
    with pytest.MonkeyPatch.context() as patch:
        first = migration_files()[:SCHEMA_THIRTEEN]
        patch.setattr(migrations, "migration_files", lambda: first)
        patch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", SCHEMA_THIRTEEN)
        assert migrate(connection) == SCHEMA_THIRTEEN


def _insert_rows(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO programs (program_id, registered_at, updated_at, owner_id) "
        f"VALUES (?, ?, ?, {OWNER})",
        (PROGRAM_ID, STAMP, STAMP),
    )
    connection.execute(
        "INSERT INTO members (project_id, program_id, rules_paths, authorize_allow, "
        "authorize_deny, registered_at, updated_at, name, owner_id) "
        f"VALUES (?, ?, '[]', '[]', '[]', ?, ?, 'forge', {OWNER})",
        (MEMBER_ID, PROGRAM_ID, STAMP, STAMP),
    )
    connection.execute(
        f"INSERT INTO machines (name, owner_id, created_at) VALUES (?, {OWNER}, ?)",
        (MACHINE_NAME, STAMP),
    )
    for session_id in ("old-1", "old-2"):
        connection.execute(
            "INSERT INTO sessions (session_id, member_id, client, directory, "
            "started_at, heartbeat_at, owner_id, machine_id) "
            f"VALUES (?, ?, 'claude', '/c', ?, ?, {OWNER}, "
            "(SELECT machine_id FROM machines))",
            (session_id, MEMBER_ID, STAMP, STAMP),
        )


def build_schema_13_store(path: Path) -> None:
    """Write a schema-13 store at ``path``: a member, a machine, two sessions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        migrate_to_thirteen(connection)
        _insert_rows(connection)
