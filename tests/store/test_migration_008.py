"""Migration 008: a populated version-7 store upgrades intact; new tables start empty.

The fixture is staged as slice 107 code would have left it — nodes, a verdict with a
finding, a check, a progress record, a watch, and a detection (the triggers wrote
feed rows) — by migrating to version 7 and writing through the store's own
statements. Then it is upgraded.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from evidence_harness import (
    check_input,
    finding,
    progress_input,
    verdict_input,
)

from amoeba.store import sql, sql_cf, sql_checks, sql_evidence, sql_feed
from amoeba.store.mapping_evidence import observation_parameters, verdict_parameters
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION, migrate
from amoeba.store.models import NodeStatus

JUDGE_SCHEMA_VERSION = 7
CF_SCHEMA_VERSION = 8

PROJECT = "demo"
STAGED_AT = "2026-10-16T00:00:00+00:00"

_PRIOR_TABLES = (
    sql.TABLE_NODES,
    sql_evidence.TABLE_VERDICTS,
    sql_evidence.TABLE_FINDING_OBSERVATIONS,
    sql_checks.TABLE_CHECK_RESULTS,
    sql_checks.TABLE_PROGRESS_RECORDS,
    sql_feed.TABLE_CHANGES,
    sql_feed.TABLE_REVIEW_WATCHES,
    sql_feed.TABLE_DETECTED_REVIEWS,
)

_NEW_TABLES = (sql_cf.TABLE_CF_LINKS, sql_cf.TABLE_CF_SNAPSHOTS)


def _insert_node(connection: sqlite3.Connection, node_id: str) -> None:
    connection.execute(
        sql.INSERT_NODE,
        (node_id, PROJECT, None, "slice", NodeStatus.RUNNABLE.value, node_id)
        + (None,) * 7
        + (STAGED_AT, STAGED_AT),
    )


def _stage_version_seven_store(path: Path) -> None:
    verdict = verdict_input("v-1", "n-1", finding("a concern"))
    with sqlite3.connect(path) as connection:
        migrate(connection, expected_version=JUDGE_SCHEMA_VERSION)
        _insert_node(connection, "n-1")
        _insert_node(connection, "n-2")
        connection.execute(
            sql_evidence.INSERT_VERDICT, verdict_parameters(verdict, PROJECT, STAGED_AT)
        )
        connection.execute(
            sql_evidence.INSERT_OBSERVATION,
            observation_parameters(verdict.id, 0, verdict.findings[0]),
        )
        connection.execute(
            sql_checks.INSERT_CHECK,
            sql_checks.check_parameters(check_input("c-1", "n-1"), PROJECT, STAGED_AT),
        )
        connection.execute(
            sql_checks.INSERT_PROGRESS,
            sql_checks.progress_parameters(
                progress_input("p-1", "n-1"), PROJECT, STAGED_AT
            ),
        )
        connection.execute(
            sql_feed.UPSERT_WATCH, (PROJECT, "/reviews", 1, STAGED_AT, STAGED_AT)
        )
        connection.execute(
            sql_feed.INSERT_DETECTION,
            (PROJECT, "/reviews/a.md", "digest", "recorded", "n-1", "v-1")
            + ("record-1", None, STAGED_AT),
        )
        connection.commit()


def _rows(connection: sqlite3.Connection, table: str) -> list[tuple[object, ...]]:
    return connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()


def _upgrade(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    assert migrate(connection, expected_version=CF_SCHEMA_VERSION) == CF_SCHEMA_VERSION
    return connection


def test_version_eight_is_the_expected_version() -> None:
    assert EXPECTED_SCHEMA_VERSION == CF_SCHEMA_VERSION


def test_upgrade_keeps_every_prior_row(store_file: Path) -> None:
    _stage_version_seven_store(store_file)
    with sqlite3.connect(store_file) as before_connection:
        before = {table: _rows(before_connection, table) for table in _PRIOR_TABLES}
    assert all(before[table] for table in _PRIOR_TABLES)  # every slice left data

    with _upgrade(store_file) as connection:
        after = {table: _rows(connection, table) for table in _PRIOR_TABLES}
    assert after == before


def test_the_new_tables_exist_and_start_empty(store_file: Path) -> None:
    _stage_version_seven_store(store_file)
    with _upgrade(store_file) as connection:
        for table in _NEW_TABLES:
            assert _rows(connection, table) == [], table


def test_columns_match_the_single_definition_site(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        for table, expected in (
            (sql_cf.TABLE_CF_LINKS, sql_cf.LINK_COLUMNS),
            (sql_cf.TABLE_CF_SNAPSHOTS, sql_cf.SNAPSHOT_COLUMNS),
        ):
            info = connection.execute(f"PRAGMA table_info({table})").fetchall()
            assert tuple(str(row[1]) for row in info) == expected, table


def test_the_snapshot_index_exists(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        names = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
    assert sql_cf.INDEX_CF_SNAPSHOTS_LINK in names
