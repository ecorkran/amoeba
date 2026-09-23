"""Migration 004: a real version-3 store upgrades intact and gains its backfill.

The fixture is staged exactly as slice 102 code would have left it — nodes, an
open human block, a resolved human block, an open judge block, and a journal
entry — by migrating to version 3 and writing through the store's own
statements. Then it is upgraded to 4.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from amoeba.store import sql, sql_inbox, sql_journal
from amoeba.store.inbox_models import Channel
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION, migrate
from amoeba.store.models import BlockedKind, NodeStatus

#: The last version before the inbox tables existed.
PRE_INBOX_SCHEMA_VERSION = 3
INBOX_SCHEMA_VERSION = 4

PROJECT = "demo"
OPEN_HUMAN_BLOCK_CREATED_AT = "2026-09-17T00:00:00+00:00"
STAGED_AT = "2026-09-16T00:00:00+00:00"


def _insert_node(
    connection: sqlite3.Connection, node_id: str, status: NodeStatus
) -> None:
    connection.execute(
        sql.INSERT_NODE,
        (node_id, PROJECT, None, "slice", status.value, node_id)
        + (None,) * 7
        + (STAGED_AT, STAGED_AT),
    )


def _insert_block(
    connection: sqlite3.Connection,
    block_id: str,
    node_id: str,
    kind: BlockedKind,
    created_at: str = STAGED_AT,
) -> None:
    connection.execute(
        sql.INSERT_BLOCKED_STATE,
        (
            block_id,
            node_id,
            kind.value,
            f"context for {block_id}",
            created_at,
            created_at,
        ),
    )


def _stage_version_three_store(path: Path) -> None:
    """A store as slice 102 left it: every kind of row migration 004 must keep."""
    with sqlite3.connect(path) as connection:
        migrate(connection, expected_version=PRE_INBOX_SCHEMA_VERSION)

        _insert_node(connection, "n-open", NodeStatus.BLOCKED_ON_HUMAN)
        _insert_block(
            connection,
            "b-open",
            "n-open",
            BlockedKind.HUMAN,
            created_at=OPEN_HUMAN_BLOCK_CREATED_AT,
        )

        _insert_node(connection, "n-resolved", NodeStatus.RUNNABLE)
        _insert_block(connection, "b-resolved", "n-resolved", BlockedKind.HUMAN)
        connection.execute(
            sql.FILL_RESOLUTION_SLOT,
            ("pm", "approved", STAGED_AT, STAGED_AT, "n-resolved"),
        )

        _insert_node(connection, "n-judge", NodeStatus.BLOCKED_ON_JUDGE)
        _insert_block(connection, "b-judge", "n-judge", BlockedKind.JUDGE)

        connection.execute(
            sql_journal.INSERT_JOURNAL_ENTRY,
            ("j-1", PROJECT, "n-open", "sq_run", "{}", STAGED_AT),
        )
        connection.commit()


def _count(connection: sqlite3.Connection, table: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0])


def _escalations(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    return connection.execute(
        sql_inbox.SELECT_MESSAGES_AFTER, (PROJECT, Channel.ESCALATION.value, 0)
    ).fetchall()


def _schema_objects(connection: sqlite3.Connection, kind: str) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = ?", (kind,)
    ).fetchall()
    return {str(row[0]) for row in rows}


def test_version_four_is_the_expected_version() -> None:
    assert EXPECTED_SCHEMA_VERSION == INBOX_SCHEMA_VERSION


def test_upgrade_keeps_every_prior_row(store_file: Path) -> None:
    _stage_version_three_store(store_file)

    with sqlite3.connect(store_file) as connection:
        assert migrate(connection) == INBOX_SCHEMA_VERSION

        assert _count(connection, sql.TABLE_NODES) == 3
        assert _count(connection, sql.TABLE_BLOCKED_STATES) == 3
        assert _count(connection, sql_journal.TABLE_COMMAND_JOURNAL) == 1

        resolved = connection.execute(
            sql.SELECT_BLOCKED_STATES_FOR_NODE, ("n-resolved",)
        ).fetchall()
        assert len(resolved) == 1


def test_upgrade_backfills_one_escalation_for_the_open_human_block_only(
    store_file: Path,
) -> None:
    """Not the resolved human block, and not the open judge block."""
    _stage_version_three_store(store_file)

    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        escalations = _escalations(connection)

    assert len(escalations) == 1
    row = escalations[0]
    assert row[sql_inbox.COL_MESSAGE_NODE_ID] == "n-open"
    assert row[sql_inbox.COL_MESSAGE_BLOCKED_STATE_ID] == "b-open"
    assert row[sql_inbox.COL_MESSAGE_PROJECT_ID] == PROJECT
    assert row[sql_inbox.COL_MESSAGE_CREATED_AT] == OPEN_HUMAN_BLOCK_CREATED_AT
    assert row[sql_inbox.COL_MESSAGE_JOURNAL_ENTRY_ID] is None
    assert row[sql_inbox.COL_MESSAGE_PAYLOAD] is None
    assert row[sql_inbox.COL_MESSAGE_ACKNOWLEDGED_AT] is None


def test_backfilled_id_has_the_shape_new_id_produces(store_file: Path) -> None:
    _stage_version_three_store(store_file)

    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        message_id = str(_escalations(connection)[0][sql_inbox.COL_MESSAGE_ID])

    assert len(message_id) == 32
    assert all(character in "0123456789abcdef" for character in message_id)


def test_fresh_store_has_both_tables_and_both_indexes(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)

        assert {
            sql_inbox.TABLE_INBOX_SUBMISSIONS,
            sql_inbox.TABLE_MESSAGES,
        } <= _schema_objects(connection, "table")
        assert {
            sql_inbox.INDEX_MESSAGES_PROJECT_CHANNEL_SEQ,
            sql_inbox.INDEX_MESSAGES_UNACKNOWLEDGED_INTENTS,
        } <= _schema_objects(connection, "index")


def test_columns_match_the_single_definition_site(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)

        for table, expected in (
            (sql_inbox.TABLE_INBOX_SUBMISSIONS, sql_inbox.SUBMISSION_COLUMNS),
            (sql_inbox.TABLE_MESSAGES, sql_inbox.MESSAGE_COLUMNS),
        ):
            columns = {
                str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")
            }
            assert columns == set(expected), table


def test_both_sequence_keys_are_autoincrement(store_file: Path) -> None:
    """AUTOINCREMENT, so a sequence value is never reassigned after a delete."""
    with sqlite3.connect(store_file) as connection:
        migrate(connection)

        for table, key in (
            (sql_inbox.TABLE_INBOX_SUBMISSIONS, sql_inbox.COL_SUBMISSION_APPLIED_SEQ),
            (sql_inbox.TABLE_MESSAGES, sql_inbox.COL_MESSAGE_SEQ),
        ):
            ddl = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            assert f"{key} integer primary key autoincrement" in str(ddl[0]).lower()


def test_unacknowledged_intent_index_is_partial(store_file: Path) -> None:
    """Asserted against the stored DDL, as the journal's partial index is.

    Which index the planner picks is a cost decision that changes with table
    statistics, so it is not pinned; the index's predicate is.
    """
    with sqlite3.connect(store_file) as connection:
        migrate(connection)

        ddl = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
            (sql_inbox.INDEX_MESSAGES_UNACKNOWLEDGED_INTENTS,),
        ).fetchone()

    statement = str(ddl[0]).lower()
    assert f"{sql_inbox.COL_MESSAGE_CHANNEL} = '{Channel.INTENT.value}'" in statement
    assert f"{sql_inbox.COL_MESSAGE_ACKNOWLEDGED_AT} is null" in statement
