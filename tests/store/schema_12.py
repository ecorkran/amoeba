"""A schema-12 store holding question, answer and wake rows (slice 262).

Modeled on ``schema_11``: migrated to 12 with the migration list cut there, then rows
inserted by plain SQL, because the seed helpers insert through the current statements
and after migration 013 those need a machine. Shared by the migration and opener tests.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Final

import pytest

from amoeba.store import migrations
from amoeba.store.migrations import migrate, migration_files

SCHEMA_TWELVE: Final = 12
OWNER: Final = "(SELECT owner_id FROM owners)"
PROGRAM_ID: Final = "demo"
MEMBER_ID: Final = "m1"
STAMP: Final = "2026-11-01T00:00:00Z"
#: Rows held by the store ``build_schema_12_store`` writes.
QUESTION_COUNT: Final = 3
WAKE_COUNT: Final = 2


def migrate_to_twelve(connection: sqlite3.Connection) -> None:
    """Bring an empty connection to schema 12 whatever the latest version is."""
    with pytest.MonkeyPatch.context() as patch:
        first = migration_files()[:SCHEMA_TWELVE]
        patch.setattr(migrations, "migration_files", lambda: first)
        patch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", SCHEMA_TWELVE)
        assert migrate(connection) == SCHEMA_TWELVE


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
    states = ("claimed", "answered", "waiting_on_pm")
    for index, state in enumerate(states):
        connection.execute(
            "INSERT INTO questions (run_id, paused_at, member_id, question, checkout, "
            "state, answering_run_id, claimed_at, updated_at, start_attempted_at, "
            f"owner_id) VALUES (?, 'p', ?, 'why?', '/c', ?, 'ans', ?, ?, ?, {OWNER})",
            (f"run-{index}", MEMBER_ID, state, STAMP, STAMP, STAMP),
        )
    connection.execute(
        "INSERT INTO answers (run_id, paused_at, answered_by, answer, recorded_at, "
        f"via, owner_id) VALUES ('run-1', 'p', 'pm', 'a', ?, 'cli', {OWNER})",
        (STAMP,),
    )
    connection.execute(
        "INSERT INTO wakes (wake_id, member_id, directory, command, started_at, "
        f"deadline_at, owner_id) VALUES ('w1', ?, '/c', 'go', ?, ?, {OWNER})",
        (MEMBER_ID, STAMP, STAMP),
    )
    connection.execute(
        "INSERT INTO wakes (wake_id, member_id, directory, command, started_at, "
        "deadline_at, log_stem, command_pid, ended_at, outcome, exit_code, detail, "
        f"owner_id) VALUES ('w2', ?, '/c', 'go', ?, ?, '/l', 7, ?, 'exited', 0, "
        f"'ok', {OWNER})",
        (MEMBER_ID, STAMP, STAMP, STAMP),
    )


def build_schema_12_store(path: Path) -> None:
    """Write a schema-12 store at ``path``: three questions, an answer, two wakes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        migrate_to_twelve(connection)
        _insert_rows(connection)
