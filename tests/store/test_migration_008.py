"""Migration 008: the ``waiting_on_request`` question state (slice 242, D2, 1.2)."""

from __future__ import annotations

import re
import sqlite3

import pytest

from amoeba.store import migrations
from amoeba.store.errors import StoreSchemaError
from amoeba.store.migrations import migrate, migration_files, read_schema_version
from amoeba.store.vocabulary import QuestionState

QUESTION_COLUMNS_007 = (
    "run_id, paused_at, member_id, question, checkout, state, answering_run_id, "
    "waiting_reason, claimed_at, updated_at, slice_label, source_commit, passages, "
    "waiting_detail, evidence, closed_reason, closed_detail, closed_at"
)
ANSWER_COLUMNS = "*"
STATES_007 = (
    QuestionState.CLAIMED,
    QuestionState.ANSWERED,
    QuestionState.WAITING_ON_PM,
)
INSERT_HELD = (
    "INSERT INTO questions (run_id, paused_at, member_id, question, checkout, state, "
    "claimed_at, updated_at, request_id) "
    "VALUES ('run-h', 'p-h', 'm1', 'q', '/c', 'waiting_on_request', 't', 't', ?)"
)


def _store_at(monkeypatch: pytest.MonkeyPatch, version: int) -> sqlite3.Connection:
    """A store holding the first ``version`` migrations, a program and a member."""
    with monkeypatch.context() as patch:
        first = migration_files()[:version]
        patch.setattr(migrations, "migration_files", lambda: first)
        patch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", version)
        connection = sqlite3.connect(":memory:", isolation_level=None)
        connection.execute("PRAGMA foreign_keys=ON")
        migrate(connection)
    connection.execute("INSERT INTO programs VALUES ('demo', NULL, NULL, 't', 't')")
    connection.execute(
        "INSERT INTO members (project_id, program_id, rules_paths, "
        "authorize_allow, authorize_deny, registered_at, updated_at) "
        "VALUES ('m1', 'demo', '[]', '[]', '[]', 't', 't')"
    )
    return connection


def _version_seven_store_with_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> sqlite3.Connection:
    """A version-7 store with a claimed, an answered and a waiting question, each
    with an answer row."""
    connection = _store_at(monkeypatch, 7)
    for index, state in enumerate(STATES_007):
        connection.execute(
            f"INSERT INTO questions ({QUESTION_COLUMNS_007}) VALUES "
            "(?, ?, 'm1', 'why?', '/c', ?, 'ans-1', 'answer_limit_reached', 't', "
            "'u', '3 s', 'abc', '[]', 'detail', '{}', NULL, NULL, NULL)",
            (f"run-{index}", f"p-{index}", state.value),
        )
        connection.execute(
            "INSERT INTO answers (run_id, paused_at, answered_by, answer, "
            "recorded_at) VALUES (?, ?, 'pm', 'text', 't')",
            (f"run-{index}", f"p-{index}"),
        )
    return connection


def _snapshot(connection: sqlite3.Connection) -> dict[str, list[tuple[object, ...]]]:
    return {
        "questions": connection.execute(
            f"SELECT {QUESTION_COLUMNS_007} FROM questions ORDER BY run_id"
        ).fetchall(),
        "answers": connection.execute(
            f"SELECT {ANSWER_COLUMNS} FROM answers ORDER BY seq"
        ).fetchall(),
    }


def _migrate_to_eight(
    connection: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> int:
    """Run the first eight migrations only, so later ones do not change the check."""
    with monkeypatch.context() as patch:
        first_eight = migration_files()[:8]
        patch.setattr(migrations, "migration_files", lambda: first_eight)
        patch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", 8)
        return migrate(connection)


def _migrated(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    connection = _version_seven_store_with_questions(monkeypatch)
    assert _migrate_to_eight(connection, monkeypatch) == 8
    return connection


def test_a_version_seven_store_migrates_with_every_row_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_seven_store_with_questions(monkeypatch)
    before = _snapshot(connection)

    assert _migrate_to_eight(connection, monkeypatch) == 8

    assert read_schema_version(connection) == 8
    assert _snapshot(connection) == before
    assert connection.execute(
        "SELECT COUNT(*) FROM questions "
        "WHERE request_id IS NULL AND start_attempted_at IS NULL"
    ).fetchone() == (len(STATES_007),)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_the_state_check_list_equals_the_enum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _migrated(monkeypatch)
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'questions'"
    ).fetchone()
    assert row is not None
    match = re.search(r"state\s+IN\s*\(([^)]*)\)", row[0])
    assert match is not None

    assert set(re.findall(r"'([^']*)'", match.group(1))) == {
        state.value for state in QuestionState
    }


def test_a_held_row_needs_a_request_id(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _migrated(monkeypatch)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(INSERT_HELD, (None,))
    connection.execute(INSERT_HELD, ("req-a",))

    assert connection.execute(
        "SELECT state, request_id FROM questions WHERE run_id = 'run-h'"
    ).fetchone() == ("waiting_on_request", "req-a")


def test_a_store_stamped_nine_is_refused_and_left_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _migrated(monkeypatch)
    connection.execute("UPDATE schema_meta SET version = 9")
    before = _snapshot(connection)

    with pytest.raises(StoreSchemaError):
        _migrate_to_eight(connection, monkeypatch)

    assert read_schema_version(connection) == 9
    assert _snapshot(connection) == before
