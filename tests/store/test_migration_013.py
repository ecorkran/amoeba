"""Migration 013: the machine on questions and wakes, the claim and start counts
(slice 262, D14)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from operations.state_move_support import make_layout

from amoeba.operations.state_move import open_state_store
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    read_schema_version,
)
from amoeba.store.vocabulary import ClosedReason, WakeOutcome
from store.schema_12 import (
    OWNER,
    QUESTION_COUNT,
    WAKE_COUNT,
    build_schema_12_store,
)

REBUILT = ("questions", "wakes")
INSERT_QUESTION = (
    "INSERT INTO questions (run_id, paused_at, member_id, question, checkout, state, "
    "claimed_at, updated_at, closed_reason, owner_id, machine_id) "
    "VALUES (?, 'p', 'm1', 'why?', '/c', 'closed', 't', 't', ?, "
    f"{OWNER}, ?)"
)
INSERT_WAKE = (
    "INSERT INTO wakes (wake_id, member_id, command, started_at, deadline_at, "
    "ended_at, outcome, owner_id, machine_id) "
    f"VALUES (?, 'm1', 'go', 't', 't', 't', ?, {OWNER}, ?)"
)
INSERT_MACHINE = (
    f"INSERT INTO machines (name, owner_id, created_at) VALUES ('m', {OWNER}, 't')"
)


def _schema_objects(connection: sqlite3.Connection) -> dict[str, set[str]]:
    """Each rebuilt table's columns, plus the names of its indexes and triggers."""
    found: dict[str, set[str]] = {}
    for table in REBUILT:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        objects = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE tbl_name = ? "
                "AND type IN ('index', 'trigger') AND name NOT LIKE 'sqlite_%'",
                (table,),
            )
        }
        found[table] = columns | objects
    return found


@pytest.fixture
def schema_12(tmp_path: Path) -> Path:
    path = tmp_path / "old.sqlite3"
    build_schema_12_store(path)
    return path


@pytest.fixture
def connection(schema_12: Path) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(schema_12, isolation_level=None)) as opened:
        opened.execute("PRAGMA foreign_keys=ON")
        yield opened


def _count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_rows_survive_and_every_column_index_and_trigger_is_carried(
    connection: sqlite3.Connection,
) -> None:
    before = _schema_objects(connection)
    counts = {table: _count(connection, table) for table in (*REBUILT, "answers")}

    assert migrate(connection) == read_schema_version(connection)
    assert read_schema_version(connection) == EXPECTED_SCHEMA_VERSION
    after = _schema_objects(connection)

    assert counts == {"questions": QUESTION_COUNT, "wakes": WAKE_COUNT, "answers": 1}
    assert {table: _count(connection, table) for table in counts} == counts
    for table in REBUILT:
        assert before[table] <= after[table], before[table] - after[table]
    assert after["questions"] - before["questions"] == {
        "machine_id",
        "start_count",
        "questions_machine_state",
        "questions_machine_required",
    }
    assert after["wakes"] - before["wakes"] == {
        "machine_id",
        "wakes_machine",
        "wakes_machine_required",
    }


def test_a_copied_row_keeps_every_value_and_gets_no_machine(
    connection: sqlite3.Connection,
) -> None:
    before = connection.execute(
        "SELECT run_id, state, start_attempted_at, owner_id FROM questions "
        "ORDER BY run_id"
    ).fetchall()
    wake = connection.execute("SELECT * FROM wakes WHERE wake_id = 'w2'").fetchone()

    migrate(connection)

    assert (
        connection.execute(
            "SELECT run_id, state, start_attempted_at, owner_id FROM questions "
            "ORDER BY run_id"
        ).fetchall()
        == before
    )
    assert connection.execute(
        "SELECT * FROM wakes WHERE wake_id = 'w2'"
    ).fetchone() == (
        *wake,
        None,
    )
    assert (
        connection.execute("SELECT machine_id, start_count FROM questions").fetchall()
        == [(None, 0)] * QUESTION_COUNT
    )
    assert connection.execute(
        "SELECT resume_claim_id, resume_start_count FROM answers"
    ).fetchall() == [(None, 0)]
    assert connection.execute("SELECT wake_wanted_at FROM messages").fetchall() == [
        (None,)
    ] * _count(connection, "messages")


def test_an_insert_with_no_machine_is_refused_on_both_tables(
    connection: sqlite3.Connection,
) -> None:
    migrate(connection)
    connection.execute(INSERT_MACHINE)

    with pytest.raises(sqlite3.IntegrityError, match="questions: machine_id"):
        connection.execute(INSERT_QUESTION, ("r-null", "dismissed", None))
    with pytest.raises(sqlite3.IntegrityError, match="wakes: machine_id"):
        connection.execute(INSERT_WAKE, ("w-null", "exited", None))


def test_machine_removed_is_accepted_by_both_check_lists(
    connection: sqlite3.Connection,
) -> None:
    migrate(connection)
    connection.execute(INSERT_MACHINE)
    machine = connection.execute("SELECT machine_id FROM machines").fetchone()[0]

    connection.execute(
        INSERT_QUESTION, ("r-gone", ClosedReason.MACHINE_REMOVED.value, machine)
    )
    connection.execute(
        INSERT_WAKE, ("w-gone", WakeOutcome.MACHINE_REMOVED.value, machine)
    )

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        connection.execute(INSERT_QUESTION, ("r-bad", "made_up", machine))
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        connection.execute(INSERT_WAKE, ("w-bad", "made_up", machine))


def test_the_opener_gives_old_rows_local_and_a_second_open_writes_nothing(
    schema_12: Path, tmp_path: Path
) -> None:
    layout = make_layout(tmp_path)
    layout.store_path.parent.mkdir(parents=True, exist_ok=True)
    schema_12.replace(layout.store_path)

    with closing(open_state_store(layout)) as store, store.read() as transaction:
        machines = transaction.execute("SELECT machine_id FROM machines").fetchall()
        local = machines[0][0]
        assert len(machines) == 1
        assert transaction.execute(
            "SELECT DISTINCT machine_id FROM questions"
        ).fetchall() == [(local,)]
        assert transaction.execute(
            "SELECT DISTINCT machine_id FROM wakes"
        ).fetchall() == [(local,)]
    before = layout.store_path.stat().st_mtime_ns
    wal = layout.store_path.with_name(layout.store_path.name + "-wal")
    wal_size = wal.stat().st_size if wal.exists() else 0

    with closing(open_state_store(layout)):
        pass

    assert layout.store_path.stat().st_mtime_ns == before
    assert (wal.stat().st_size if wal.exists() else 0) == wal_size
