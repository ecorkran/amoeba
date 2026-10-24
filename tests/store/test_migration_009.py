"""Migration 009: a populated version-8 store upgrades intact.

The Runner tables start empty.

The fixture is staged as slice 110 code would have left it — a node, an
acknowledged intent, an unacknowledged intent and a node escalation — by
migrating to version 8 and writing through the store's own statements. Then it
is upgraded.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from legacy_nodes import LEGACY_INSERT_NODE

from amoeba.store import Store, sql_inbox, sql_runner
from amoeba.store.inbox_models import Channel
from amoeba.store.mapping_inbox import map_message
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION, migrate
from amoeba.store.models import (
    NodeStatus,
    StoreSchemaError,
    UnknownVocabularyValueError,
)

PRIOR_SCHEMA_VERSION = 8
RUNNER_SCHEMA_VERSION = 9

PROJECT = "demo"
STAGED_AT = "2026-10-22T00:00:00+00:00"

_NEW_TABLES = (
    sql_runner.TABLE_ROUTING_TABLE_VERSIONS,
    sql_runner.TABLE_ROUTING_DECISIONS,
    sql_runner.TABLE_ATTEMPT_COUNTS,
    sql_runner.TABLE_DESIRED_STATES,
)

_NEW_MESSAGE_COLUMNS = (
    sql_inbox.COL_MESSAGE_ACKNOWLEDGMENT_OUTCOME,
    sql_inbox.COL_MESSAGE_ACKNOWLEDGMENT_REASON,
    sql_inbox.COL_MESSAGE_FAULT_KIND,
    sql_inbox.COL_MESSAGE_CLOSED_AT,
    sql_inbox.COL_MESSAGE_CLOSED_BY,
)

#: The version-8 columns of ``messages``, which are what a staged row has.
_OLD_MESSAGE_WIDTH = len(sql_inbox.MESSAGE_COLUMNS) - len(_NEW_MESSAGE_COLUMNS)


def _insert_message(
    connection: sqlite3.Connection,
    message_id: str,
    channel: Channel,
    *,
    node_id: str | None = None,
    fault_kind: str | None = None,
    closed_at: str | None = None,
) -> None:
    """Insert one row through the 004 statement, then set any 009 column."""
    connection.execute(
        sql_inbox.INSERT_MESSAGE,
        (
            message_id,
            PROJECT,
            channel.value,
            node_id,
            None,
            None,
            None,
            "{}",
            STAGED_AT,
        ),
    )
    connection.execute(
        f"UPDATE {sql_inbox.TABLE_MESSAGES} SET "
        f"{sql_inbox.COL_MESSAGE_FAULT_KIND} = ?, "
        f"{sql_inbox.COL_MESSAGE_CLOSED_AT} = ? "
        f"WHERE {sql_inbox.COL_MESSAGE_ID} = ?",
        (fault_kind, closed_at, message_id),
    )


def _stage_version_eight_store(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        migrate(connection, expected_version=PRIOR_SCHEMA_VERSION)
        connection.execute(
            LEGACY_INSERT_NODE,
            ("n-1", PROJECT, None, "slice", NodeStatus.RUNNABLE.value, "n-1")
            + (None,) * 7
            + (STAGED_AT, STAGED_AT),
        )
        connection.execute(
            sql_inbox.INSERT_MESSAGE,
            ("m-acked", PROJECT, "intent", None, None, None, "s-1", "{}", STAGED_AT),
        )
        connection.execute(
            "UPDATE messages SET acknowledged_at = ?, acknowledged_by = ? WHERE id = ?",
            (STAGED_AT, "runner", "m-acked"),
        )
        connection.execute(
            sql_inbox.INSERT_MESSAGE,
            ("m-open", PROJECT, "intent", None, None, None, "s-2", "{}", STAGED_AT),
        )
        connection.execute(
            sql_inbox.INSERT_MESSAGE,
            ("m-esc", PROJECT, "escalation", "n-1", None, None, None, None, STAGED_AT),
        )
        connection.commit()


def _rows(connection: sqlite3.Connection, table: str) -> list[tuple[object, ...]]:
    return connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()


def _upgrade(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    assert migrate(connection, expected_version=RUNNER_SCHEMA_VERSION) == (
        RUNNER_SCHEMA_VERSION
    )
    return connection


@pytest.fixture
def migrated(store_file: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(store_file)
    migrate(connection)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def test_the_expected_version_is_at_least_nine() -> None:
    assert EXPECTED_SCHEMA_VERSION >= RUNNER_SCHEMA_VERSION


def test_upgrade_keeps_old_rows_and_leaves_the_new_columns_null(
    store_file: Path,
) -> None:
    _stage_version_eight_store(store_file)
    with sqlite3.connect(store_file) as before_connection:
        before = _rows(before_connection, sql_inbox.TABLE_MESSAGES)
    assert len(before) == 3

    with _upgrade(store_file) as connection:
        after = _rows(connection, sql_inbox.TABLE_MESSAGES)

    assert [row[:_OLD_MESSAGE_WIDTH] for row in after] == before
    assert all(row[_OLD_MESSAGE_WIDTH:] == (None,) * 5 for row in after)


def test_old_rows_read_back_through_the_store(store_file: Path) -> None:
    _stage_version_eight_store(store_file)
    with Store.open(store_file) as store:
        intents = store.messages(PROJECT, channel=Channel.INTENT)
        assert [message.id for message in intents] == ["m-acked", "m-open"]
        assert intents[0].is_acknowledged
        assert intents[0].acknowledgment_outcome is None
        assert [message.id for message in store.pending_intents(PROJECT)] == ["m-open"]


def test_the_new_tables_exist_and_start_empty(store_file: Path) -> None:
    _stage_version_eight_store(store_file)
    with _upgrade(store_file) as connection:
        for table in _NEW_TABLES:
            assert _rows(connection, table) == [], table


def test_columns_match_the_single_definition_sites(
    migrated: sqlite3.Connection,
) -> None:
    for table, expected in (
        (sql_inbox.TABLE_MESSAGES, sql_inbox.MESSAGE_COLUMNS),
        (sql_runner.TABLE_ROUTING_TABLE_VERSIONS, sql_runner.TABLE_VERSION_COLUMNS),
        (sql_runner.TABLE_ROUTING_DECISIONS, sql_runner.DECISION_COLUMNS),
        (sql_runner.TABLE_ATTEMPT_COUNTS, sql_runner.ATTEMPT_COLUMNS),
        (sql_runner.TABLE_DESIRED_STATES, sql_runner.DESIRED_STATE_COLUMNS),
    ):
        info = migrated.execute(f"PRAGMA table_info({table})").fetchall()
        assert tuple(str(row[1]) for row in info) == expected, table


def test_the_named_indexes_exist(migrated: sqlite3.Connection) -> None:
    names = {
        str(row[0])
        for row in migrated.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    assert {
        sql_inbox.INDEX_MESSAGES_OPEN_PROJECT_ESCALATION,
        sql_runner.INDEX_DECISIONS_ENTRY,
        sql_runner.INDEX_DECISIONS_NODE,
        sql_runner.INDEX_DESIRED_PROJECT_TARGET,
        sql_runner.INDEX_DESIRED_NODE_TARGET,
    } <= names


# --------------------------------------------------------------------------
# The open-escalation partial unique index
# --------------------------------------------------------------------------


def test_a_second_open_escalation_for_one_fault_is_refused(
    migrated: sqlite3.Connection,
) -> None:
    _insert_message(migrated, "e-1", Channel.ESCALATION, fault_kind="plan")
    with pytest.raises(sqlite3.IntegrityError):
        _insert_message(migrated, "e-2", Channel.ESCALATION, fault_kind="plan")


def test_a_second_escalation_is_allowed_once_the_first_is_closed(
    migrated: sqlite3.Connection,
) -> None:
    _insert_message(
        migrated, "e-1", Channel.ESCALATION, fault_kind="plan", closed_at=STAGED_AT
    )
    _insert_message(migrated, "e-2", Channel.ESCALATION, fault_kind="plan")


def test_the_index_ignores_rows_without_a_fault_kind(
    migrated: sqlite3.Connection,
) -> None:
    _insert_message(migrated, "e-1", Channel.ESCALATION)
    _insert_message(migrated, "e-2", Channel.ESCALATION)


# --------------------------------------------------------------------------
# desired_states and routing_decisions indexes
# --------------------------------------------------------------------------

_INSERT_DESIRED = (
    f"INSERT INTO {sql_runner.TABLE_DESIRED_STATES} "
    f"({', '.join(sql_runner.DESIRED_STATE_COLUMNS)}) "
    "VALUES (?, ?, ?, 1, NULL, NULL, ?, ?)"
)


def _stage_node_and_intent(connection: sqlite3.Connection) -> None:
    connection.execute(
        LEGACY_INSERT_NODE,
        ("n-1", PROJECT, None, "slice", NodeStatus.RUNNABLE.value, "n-1")
        + (None,) * 7
        + (STAGED_AT, STAGED_AT),
    )
    _insert_message(connection, "m-1", Channel.INTENT)


def test_desired_states_allow_one_row_per_target(migrated: sqlite3.Connection) -> None:
    _stage_node_and_intent(migrated)
    migrated.execute(_INSERT_DESIRED, ("d-1", PROJECT, None, "m-1", STAGED_AT))
    migrated.execute(_INSERT_DESIRED, ("d-2", PROJECT, "n-1", "m-1", STAGED_AT))

    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(_INSERT_DESIRED, ("d-3", PROJECT, None, "m-1", STAGED_AT))
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(_INSERT_DESIRED, ("d-4", PROJECT, "n-1", "m-1", STAGED_AT))


def _insert_decision(
    connection: sqlite3.Connection, decision_id: str, entry_id: str | None
) -> None:
    columns = sql_runner.DECISION_COLUMNS
    connection.execute(
        f"INSERT INTO {sql_runner.TABLE_ROUTING_DECISIONS} ({', '.join(columns)}) "
        f"VALUES ({', '.join('?' * len(columns))})",
        (decision_id, PROJECT, "n-1", entry_id, "{}", "rule", "v1", "0.1")
        + ("advance", "{}", None, None, STAGED_AT),
    )


def test_a_journal_entry_is_routed_at_most_once(migrated: sqlite3.Connection) -> None:
    _stage_node_and_intent(migrated)
    migrated.execute(
        f"INSERT INTO {sql_runner.TABLE_ROUTING_TABLE_VERSIONS} "
        f"({', '.join(sql_runner.TABLE_VERSION_COLUMNS)}) VALUES (?, ?, ?)",
        ("v1", "table", STAGED_AT),
    )
    migrated.execute(
        "INSERT INTO command_journal (id, project_id, node_id, kind, parameters, "
        "issued_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("j-1", PROJECT, "n-1", "sq_run", "{}", STAGED_AT),
    )

    _insert_decision(migrated, "r-1", "j-1")
    with pytest.raises(sqlite3.IntegrityError):
        _insert_decision(migrated, "r-2", "j-1")

    # A decision with no entry may repeat.
    _insert_decision(migrated, "r-3", None)
    _insert_decision(migrated, "r-4", None)


# --------------------------------------------------------------------------
# Read-only open and mapping
# --------------------------------------------------------------------------


def test_a_read_only_open_of_a_version_eight_file_is_refused(store_file: Path) -> None:
    _stage_version_eight_store(store_file)
    with pytest.raises(StoreSchemaError):
        Store.open_read_only(store_file)


def test_map_message_refuses_an_unknown_stored_outcome() -> None:
    row = (1, "m", PROJECT, "intent", None, None, None, None, None, STAGED_AT)
    row += (None, None, "maybe", None, None, None, None)
    with pytest.raises(UnknownVocabularyValueError, match="AcknowledgmentOutcome"):
        map_message(row)


def test_map_message_refuses_a_row_of_the_wrong_width() -> None:
    row = (1, "m", PROJECT, "intent", None, None, None, None, None, STAGED_AT)
    with pytest.raises(UnknownVocabularyValueError, match="columns"):
        map_message(row + (None,) * (len(sql_inbox.MESSAGE_COLUMNS) - 11))
