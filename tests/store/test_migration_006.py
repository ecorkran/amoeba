"""Migration 006: a populated version-5 store upgrades intact; the feed starts empty.

The fixture is staged as slice 105 code would have left it — nodes, a journal
entry, an inbox submission, a message, and a verdict with a finding — by
migrating to version 5 and writing through the store's own statements. Then it
is upgraded to 6.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from evidence_harness import finding, pre_judge_verdict_insert, verdict_input
from legacy_nodes import LEGACY_INSERT_NODE

from amoeba.store import sql, sql_evidence, sql_feed, sql_inbox, sql_journal
from amoeba.store.mapping_evidence import observation_parameters
from amoeba.store.migrations import migrate
from amoeba.store.models import NodeStatus

EVIDENCE_SCHEMA_VERSION = 5
FEED_SCHEMA_VERSION = 6

PROJECT = "demo"
STAGED_AT = "2026-10-15T00:00:00+00:00"

_PRIOR_TABLES = (
    sql.TABLE_NODES,
    sql_journal.TABLE_COMMAND_JOURNAL,
    sql_inbox.TABLE_INBOX_SUBMISSIONS,
    sql_inbox.TABLE_MESSAGES,
    sql_evidence.TABLE_VERDICTS,
    sql_evidence.TABLE_FINDING_OBSERVATIONS,
)

_NEW_TABLES = (
    sql_feed.TABLE_CHANGES,
    sql_feed.TABLE_REVIEW_WATCHES,
    sql_feed.TABLE_DETECTED_REVIEWS,
)


def _insert_node(connection: sqlite3.Connection, node_id: str) -> None:
    connection.execute(
        LEGACY_INSERT_NODE,
        (node_id, PROJECT, None, "slice", NodeStatus.RUNNABLE.value, node_id)
        + (None,) * 7
        + (STAGED_AT, STAGED_AT),
    )


def _stage_version_five_store(path: Path) -> None:
    verdict = verdict_input("v-1", "n-1", finding("a concern"))
    with sqlite3.connect(path) as connection:
        migrate(connection, expected_version=EVIDENCE_SCHEMA_VERSION)
        _insert_node(connection, "n-1")
        _insert_node(connection, "n-2")
        connection.execute(
            sql_journal.INSERT_JOURNAL_ENTRY,
            ("j-1", PROJECT, "n-1", "sq_run", "{}", STAGED_AT),
        )
        connection.execute(
            sql_inbox.INSERT_SUBMISSION,
            (
                "s-1",
                PROJECT,
                "intent",
                "pm",
                STAGED_AT,
                "{}",
                "applied",
                None,
                STAGED_AT,
            ),
        )
        connection.execute(
            sql_inbox.INSERT_MESSAGE,
            ("m-1", PROJECT, "intent", "n-1", None, None, "s-1", "{}", STAGED_AT),
        )
        connection.execute(*pre_judge_verdict_insert(verdict, PROJECT, STAGED_AT))
        connection.execute(
            sql_evidence.INSERT_OBSERVATION,
            observation_parameters(verdict.id, 0, verdict.findings[0]),
        )
        connection.commit()


def _rows(connection: sqlite3.Connection, table: str) -> list[tuple[object, ...]]:
    return connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()


def test_upgrade_keeps_every_prior_row(store_file: Path) -> None:
    _stage_version_five_store(store_file)
    with sqlite3.connect(store_file) as connection:
        before = {table: _rows(connection, table) for table in _PRIOR_TABLES}
        assert (
            migrate(connection, expected_version=FEED_SCHEMA_VERSION)
            == FEED_SCHEMA_VERSION
        )
        after = {table: _rows(connection, table) for table in _PRIOR_TABLES}

    assert [len(before[table]) for table in _PRIOR_TABLES] == [2, 1, 1, 1, 1, 1]
    assert after == before


def test_the_new_tables_exist_and_start_empty(store_file: Path) -> None:
    _stage_version_five_store(store_file)
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        for table in _NEW_TABLES:
            assert _rows(connection, table) == [], table


def test_columns_match_the_single_definition_site(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        for table, expected in (
            (sql_feed.TABLE_CHANGES, sql_feed.CHANGE_COLUMNS),
            (sql_feed.TABLE_REVIEW_WATCHES, sql_feed.WATCH_COLUMNS),
            (sql_feed.TABLE_DETECTED_REVIEWS, sql_feed.DETECTION_COLUMNS),
        ):
            info = connection.execute(f"PRAGMA table_info({table})").fetchall()
            assert tuple(str(row[1]) for row in info) == expected, table


def test_the_change_cursor_index_exists(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        names = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
    assert sql_feed.INDEX_CHANGES_PROJECT_SEQ in names
