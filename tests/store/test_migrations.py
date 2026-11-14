"""Migration discovery and the runner (slice 222, D4)."""

from __future__ import annotations

import sqlite3
from importlib import resources

import pytest

from amoeba.store import migrations
from amoeba.store.errors import StoreCorruptError, StoreSchemaError
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    migration_files,
    read_schema_version,
    split_statements,
)


def _empty_database() -> sqlite3.Connection:
    return sqlite3.connect(":memory:", isolation_level=None)


def test_expected_version_is_the_highest_numbered_file() -> None:
    names = [
        entry.name
        for entry in (resources.files("amoeba.store") / "schema").iterdir()
        if entry.name.endswith(".sql")
    ]

    assert EXPECTED_SCHEMA_VERSION == max(int(name[:3]) for name in names)
    assert [version for version, _ in migration_files()] == list(
        range(1, EXPECTED_SCHEMA_VERSION + 1)
    )


def test_migrating_an_empty_database_stamps_the_version() -> None:
    connection = _empty_database()
    assert read_schema_version(connection) == 0

    assert migrate(connection) == EXPECTED_SCHEMA_VERSION

    assert read_schema_version(connection) == EXPECTED_SCHEMA_VERSION
    assert not connection.in_transaction


def test_migrating_twice_applies_nothing_the_second_time() -> None:
    connection = _empty_database()
    migrate(connection)

    assert migrate(connection) == EXPECTED_SCHEMA_VERSION


def test_a_newer_stamp_raises_and_rolls_back() -> None:
    connection = _empty_database()
    migrate(connection)
    connection.execute("UPDATE schema_meta SET version = 50")

    with pytest.raises(StoreSchemaError):
        migrate(connection)

    assert not connection.in_transaction
    assert read_schema_version(connection) == 50


def test_split_statements_keeps_quoted_semicolons_and_comments() -> None:
    script = (
        "-- one\nCREATE TABLE a (x TEXT DEFAULT ';');\n\n"
        "INSERT INTO a VALUES ('y');\n-- end\n"
    )

    assert split_statements(script) == [
        "-- one\nCREATE TABLE a (x TEXT DEFAULT ';');",
        "INSERT INTO a VALUES ('y');",
    ]


def test_split_statements_refuses_a_dangling_statement() -> None:
    with pytest.raises(StoreSchemaError):
        split_statements("CREATE TABLE a (x TEXT)")


NEW_QUESTION_COLUMNS = (
    "slice_label",
    "source_commit",
    "passages",
    "waiting_detail",
    "evidence",
)
NEW_ANSWER_COLUMNS = ("cited", "resume_detail", "resume_log", "resume_at")


def _version_one_store_with_rows() -> sqlite3.Connection:
    """A store as slice 222 left it: migration 001 only, one question and answer."""
    connection = _empty_database()
    connection.execute("PRAGMA foreign_keys=ON")
    first_version, first_script = migration_files()[0]
    assert first_version == 1
    for statement in split_statements(first_script):
        connection.execute(statement)
    connection.execute(
        "INSERT INTO schema_meta (id, version) VALUES (1, ?)", (first_version,)
    )
    connection.execute("INSERT INTO programs VALUES ('demo', NULL, NULL, 't', 't')")
    connection.execute(
        "INSERT INTO members (project_id, program_id, rules_paths, authorize_allow, "
        "authorize_deny, registered_at, updated_at) "
        "VALUES ('m1', 'demo', '[]', '[]', '[]', 't', 't')"
    )
    connection.execute(
        "INSERT INTO questions (run_id, paused_at, member_id, question, checkout, "
        "state, claimed_at, updated_at) "
        "VALUES ('r1', 'p1', 'm1', 'why?', '/c', 'answered', 't', 't')"
    )
    connection.execute(
        "INSERT INTO answers (run_id, paused_at, answered_by, answer, recorded_at) "
        "VALUES ('r1', 'p1', 'pm', 'because', 't')"
    )
    return connection


def test_a_version_one_store_migrates_forward_with_its_rows_intact() -> None:
    connection = _version_one_store_with_rows()
    assert read_schema_version(connection) == 1

    assert migrate(connection) == EXPECTED_SCHEMA_VERSION

    assert read_schema_version(connection) == EXPECTED_SCHEMA_VERSION
    question = connection.execute(
        f"SELECT question, state, {', '.join(NEW_QUESTION_COLUMNS)} FROM questions"
    ).fetchall()
    assert question == [("why?", "answered", None, None, None, None, None)]
    answer = connection.execute(
        f"SELECT answer, answered_by, {', '.join(NEW_ANSWER_COLUMNS)} FROM answers"
    ).fetchall()
    assert answer == [("because", "pm", None, None, None, None)]


DANGLING_MIGRATION = """
INSERT INTO questions (run_id, paused_at, member_id, question, checkout, state,
                       claimed_at, updated_at)
VALUES ('r9', 'p9', 'no-such-member', 'why?', '/c', 'claimed', 't', 't');
"""
FOREIGN_KEYS_PRAGMA = "PRAGMA foreign_keys"


def _with_extra_migration(monkeypatch: pytest.MonkeyPatch, script: str) -> int:
    """Make the runner see one more migration; returns its version."""
    real = migration_files()
    version = EXPECTED_SCHEMA_VERSION + 1
    monkeypatch.setattr(
        migrations, "migration_files", lambda: [*real, (version, script)]
    )
    monkeypatch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", version)
    return version


def test_a_migration_leaving_a_dangling_foreign_key_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _empty_database()
    connection.execute("PRAGMA foreign_keys=ON")
    old_version = migrate(connection)
    _with_extra_migration(monkeypatch, DANGLING_MIGRATION)

    with pytest.raises(StoreCorruptError, match="dangling foreign key"):
        migrations.migrate(connection)

    assert not connection.in_transaction
    assert read_schema_version(connection) == old_version
    assert connection.execute("SELECT COUNT(*) FROM questions").fetchone() == (0,)
    assert connection.execute(FOREIGN_KEYS_PRAGMA).fetchone() == (1,)


def test_foreign_keys_are_off_during_a_migration_and_on_afterward(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _empty_database()
    connection.execute("PRAGMA foreign_keys=ON")
    migrate(connection)
    # A clean migration that records the pragma value it ran under.
    version = _with_extra_migration(
        monkeypatch,
        "CREATE TABLE seen_pragma AS SELECT foreign_keys AS value "
        "FROM pragma_foreign_keys;\n",
    )

    assert migrations.migrate(connection) == version

    assert connection.execute("SELECT value FROM seen_pragma").fetchall() == [(0,)]
    assert connection.execute(FOREIGN_KEYS_PRAGMA).fetchone() == (1,)


def test_migrations_one_and_two_apply_to_a_new_store_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_two = migration_files()[:2]
    monkeypatch.setattr(migrations, "migration_files", lambda: first_two)
    monkeypatch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", 2)
    connection = _empty_database()

    assert migrations.migrate(connection) == 2

    columns = {row[1] for row in connection.execute("PRAGMA table_info(questions)")}
    assert {"state", "waiting_reason", *NEW_QUESTION_COLUMNS} <= columns
    assert read_schema_version(connection) == 2


QUESTION_OLD_COLUMNS = (
    "run_id, paused_at, member_id, question, checkout, state, answering_run_id, "
    "waiting_reason, claimed_at, updated_at, slice_label, source_commit, passages, "
    "waiting_detail, evidence"
)
ANSWER_OLD_COLUMNS = (
    "seq, run_id, paused_at, answered_by, answer, recorded_at, resume_outcome, "
    "cited, resume_detail, resume_log, resume_at"
)
MEMBER_OLD_COLUMNS = (
    "project_id, program_id, rules_paths, authorize_allow, authorize_deny, "
    "registered_at, updated_at"
)
PAIR_OLD_COLUMNS = (
    "program_id, provider_id, consumer_id, consumed, registered_at, updated_at"
)
NEW_COLUMNS_003 = {
    "questions": ("closed_reason", "closed_detail", "closed_at"),
    "answers": ("retracted_at", "retract_reason", "resume_started_at"),
    "members": ("removed_at",),
}


def _version_two_store_with_every_state(
    monkeypatch: pytest.MonkeyPatch,
) -> sqlite3.Connection:
    """A store at version 2 holding every question state, both answer kinds with
    each resume outcome, two members and a pair."""
    with monkeypatch.context() as patch:
        first_two = migration_files()[:2]
        patch.setattr(migrations, "migration_files", lambda: first_two)
        patch.setattr(migrations, "EXPECTED_SCHEMA_VERSION", 2)
        connection = _empty_database()
        connection.execute("PRAGMA foreign_keys=ON")
        migrations.migrate(connection)
    connection.execute("INSERT INTO programs VALUES ('demo', NULL, NULL, 't', 't')")
    for member in ("m1", "m2"):
        connection.execute(
            "INSERT INTO members (project_id, program_id, rules_paths, "
            "authorize_allow, authorize_deny, registered_at, updated_at) "
            "VALUES (?, 'demo', '[\"CLAUDE.md\"]', '[]', '[]', 't', 't')",
            (member,),
        )
    connection.execute(
        "INSERT INTO dependency_pairs VALUES ('demo', 'm1', 'm2', 'from_source', 't', "
        "'t')"
    )
    states = ("claimed", "answered", "waiting_on_pm")
    for index, state in enumerate(states):
        connection.execute(
            f"INSERT INTO questions ({QUESTION_OLD_COLUMNS}) VALUES "
            "(?, ?, 'm1', 'why?', '/c', ?, 'ans-1', 'answer_limit_reached', 't', 'u', "
            "'3 s', 'abc', '[]', 'detail', '{}')",
            (f"run-{index}", f"p-{index}", state),
        )
    outcomes = (None, "resumed", "refused", "not_delivered")
    for outcome in outcomes:
        for answered_by in ("answerer", "pm"):
            connection.execute(
                f"INSERT INTO answers ({ANSWER_OLD_COLUMNS}) VALUES "
                "(NULL, 'run-1', 'p-1', ?, 'text', 't', ?, '[\"c1\"]', 'why', "
                "'/log', 'r')",
                (answered_by, outcome),
            )
    return connection


def _snapshot(connection: sqlite3.Connection) -> dict[str, list[tuple[object, ...]]]:
    return {
        "questions": connection.execute(
            f"SELECT {QUESTION_OLD_COLUMNS} FROM questions ORDER BY run_id"
        ).fetchall(),
        "answers": connection.execute(
            f"SELECT {ANSWER_OLD_COLUMNS} FROM answers ORDER BY seq"
        ).fetchall(),
        "members": connection.execute(
            f"SELECT {MEMBER_OLD_COLUMNS} FROM members ORDER BY project_id"
        ).fetchall(),
        "pairs": connection.execute(
            f"SELECT {PAIR_OLD_COLUMNS} FROM dependency_pairs"
        ).fetchall(),
    }


def test_a_version_two_store_migrates_to_three_with_every_row_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_two_store_with_every_state(monkeypatch)
    before = _snapshot(connection)
    assert read_schema_version(connection) == 2

    assert migrate(connection) == EXPECTED_SCHEMA_VERSION

    assert read_schema_version(connection) == EXPECTED_SCHEMA_VERSION
    assert _snapshot(connection) == before
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute(FOREIGN_KEYS_PRAGMA).fetchone() == (1,)
    for table, columns in NEW_COLUMNS_003.items():
        nulls = " AND ".join(f"{column} IS NULL" for column in columns)
        total = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        assert total is not None and total[0] > 0
        assert (
            connection.execute(f"SELECT COUNT(*) FROM {table} WHERE {nulls}").fetchone()
            == total
        )


def test_the_rebuilt_questions_table_keeps_the_key_answers_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _version_two_store_with_every_state(monkeypatch)
    migrate(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            f"INSERT INTO answers ({ANSWER_OLD_COLUMNS}) VALUES "
            "(NULL, 'run-x', 'p-x', 'pm', 'orphan', 't', NULL, NULL, NULL, NULL, NULL)"
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO questions (run_id, paused_at, member_id, question, checkout, "
            "state, claimed_at, updated_at) "
            "VALUES ('run-0', 'p-0', 'm1', 'dup', '/c', 'claimed', 't', 't')"
        )


def test_a_closed_question_needs_a_known_reason() -> None:
    connection = _empty_database()
    connection.execute("PRAGMA foreign_keys=ON")
    migrate(connection)
    connection.execute("INSERT INTO programs VALUES ('demo', NULL, NULL, 't', 't')")
    connection.execute(
        "INSERT INTO members (project_id, program_id, rules_paths, authorize_allow, "
        "authorize_deny, registered_at, updated_at, removed_at) "
        "VALUES ('m1', 'demo', '[]', '[]', '[]', 't', 't', NULL)"
    )
    insert = (
        "INSERT INTO questions (run_id, paused_at, member_id, question, checkout, "
        "state, claimed_at, updated_at, closed_reason) "
        "VALUES (?, 'p', 'm1', 'why?', '/c', 'closed', 't', 't', ?)"
    )

    connection.execute(insert, ("good", "run_gone"))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(insert, ("bad", "made_up"))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO questions (run_id, paused_at, member_id, question, "
            "checkout, state, claimed_at, updated_at) "
            "VALUES ('odd', 'p', 'm1', 'why?', '/c', 'not_a_state', 't', 't')"
        )
