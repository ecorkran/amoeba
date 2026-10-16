"""Migration 007: a populated version-6 store upgrades intact; new tables start empty.

The fixture is staged as slice 106 code would have left it — nodes, a verdict with
a finding (whose trigger wrote feed rows), a watch, and a detection — by migrating
to version 6 and writing through the store's own statements. Then it is upgraded.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from evidence_harness import finding, pre_judge_verdict_insert, verdict_input

from amoeba.store import sql, sql_checks, sql_evidence, sql_feed
from amoeba.store.check_models import CheckOutcome, CheckStanding
from amoeba.store.mapping_evidence import observation_parameters
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION, migrate
from amoeba.store.models import NodeStatus, UnknownVocabularyValueError

FEED_SCHEMA_VERSION = 6
JUDGE_SCHEMA_VERSION = 7

PROJECT = "demo"
STAGED_AT = "2026-10-15T00:00:00+00:00"

_PRIOR_TABLES = (
    sql.TABLE_NODES,
    sql_evidence.TABLE_FINDING_OBSERVATIONS,
    sql_feed.TABLE_CHANGES,
    sql_feed.TABLE_REVIEW_WATCHES,
    sql_feed.TABLE_DETECTED_REVIEWS,
)

_NEW_TABLES = (sql_checks.TABLE_CHECK_RESULTS, sql_checks.TABLE_PROGRESS_RECORDS)


def _insert_node(connection: sqlite3.Connection, node_id: str) -> None:
    connection.execute(
        sql.INSERT_NODE,
        (node_id, PROJECT, None, "slice", NodeStatus.RUNNABLE.value, node_id)
        + (None,) * 7
        + (STAGED_AT, STAGED_AT),
    )


def _stage_version_six_store(path: Path) -> None:
    verdict = verdict_input("v-1", "n-1", finding("a concern"))
    with sqlite3.connect(path) as connection:
        migrate(connection, expected_version=FEED_SCHEMA_VERSION)
        _insert_node(connection, "n-1")
        _insert_node(connection, "n-2")
        connection.execute(*pre_judge_verdict_insert(verdict, PROJECT, STAGED_AT))
        connection.execute(
            sql_evidence.INSERT_OBSERVATION,
            observation_parameters(verdict.id, 0, verdict.findings[0]),
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
    assert (
        migrate(connection, expected_version=JUDGE_SCHEMA_VERSION)
        == JUDGE_SCHEMA_VERSION
    )
    return connection


def test_version_seven_is_the_expected_version() -> None:
    assert EXPECTED_SCHEMA_VERSION == JUDGE_SCHEMA_VERSION


def test_upgrade_keeps_every_prior_row_and_nulls_the_new_column(
    store_file: Path,
) -> None:
    _stage_version_six_store(store_file)
    with sqlite3.connect(store_file) as before_connection:
        before = {table: _rows(before_connection, table) for table in _PRIOR_TABLES}
        verdicts_before = _rows(before_connection, sql_evidence.TABLE_VERDICTS)

    with _upgrade(store_file) as connection:
        after = {table: _rows(connection, table) for table in _PRIOR_TABLES}
        verdicts_after = _rows(connection, sql_evidence.TABLE_VERDICTS)
        invocation = connection.execute(
            f"SELECT {sql_evidence.COL_VERDICT_JUDGE_INVOCATION_ID} "
            f"FROM {sql_evidence.TABLE_VERDICTS}"
        ).fetchall()

    assert [len(before[table]) for table in _PRIOR_TABLES] == [
        2,
        1,
        4,
        1,
        1,
    ]  # triggers wrote the changes
    assert after == before
    # The verdict gains exactly one trailing column, and it is NULL.
    assert [row[:-1] for row in verdicts_after] == verdicts_before
    assert invocation == [(None,)]


def test_the_new_tables_exist_and_start_empty(store_file: Path) -> None:
    _stage_version_six_store(store_file)
    with _upgrade(store_file) as connection:
        for table in _NEW_TABLES:
            assert _rows(connection, table) == [], table


def test_columns_match_the_single_definition_site(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        for table, expected in (
            (sql_checks.TABLE_CHECK_RESULTS, sql_checks.CHECK_COLUMNS),
            (
                sql_checks.TABLE_PROGRESS_RECORDS,
                (sql_checks.COL_PROGRESS_RECORDED_SEQ,)
                + sql_checks.PROGRESS_INSERT_COLUMNS,
            ),
        ):
            info = connection.execute(f"PRAGMA table_info({table})").fetchall()
            assert tuple(str(row[1]) for row in info) == expected, table


def test_the_indexes_exist(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        names = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
    assert {
        sql_checks.INDEX_CHECK_RESULTS_NODE,
        sql_checks.INDEX_PROGRESS_RECORDS_NODE,
        sql_checks.INDEX_VERDICTS_JUDGE_INVOCATION,
    } <= names


def _check_row(outcome: str = "passed") -> tuple[object, ...]:
    return (
        1,
        "c-1",
        PROJECT,
        "n-1",
        "cf check",
        outcome,
        3,
        '{"files": 3}',
        "abc123",
        "context-forge",
        "1.2.3",
        "command_output",
        None,
        STAGED_AT,
    )


def test_a_check_row_maps_to_a_record() -> None:
    record = sql_checks.map_check(_check_row())
    assert record.outcome is CheckOutcome.PASSED
    assert record.standing is CheckStanding.PASSED
    assert record.examined == {"files": 3}
    assert record.baseline_ref == "abc123"
    assert record.provenance.source_path is None


def test_an_unknown_outcome_raises_rather_than_defaulting() -> None:
    with pytest.raises(UnknownVocabularyValueError, match="maybe"):
        sql_checks.map_check(_check_row("maybe"))
