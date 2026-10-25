"""Migration 012: resolution decisions and the Runner's answer on blocked states.

A populated version-11 store upgrades intact, every existing row reads null in the
six new columns, and the partial index exists. The index's use is asserted with
the store methods in ``test_resolutions.py``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from legacy_nodes import LEGACY_FILL_RESOLUTION_SLOT, LEGACY_INSERT_NODE

from amoeba.store import sql
from amoeba.store.mapping import map_blocked_state
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    read_schema_version,
)
from amoeba.store.models import (
    NodeStatus,
    ResolutionOutcome,
    UnknownVocabularyValueError,
)

PRIOR_SCHEMA_VERSION = 11
DECISIONS_SCHEMA_VERSION = 12

PROJECT = "demo"
STAGED_AT = "2026-10-25T00:00:00+00:00"
NEW_COLUMNS = (
    sql.COL_BLOCKED_RESOLUTION_DECISION,
    sql.COL_BLOCKED_RESOLUTION_INSTRUCTIONS,
    sql.COL_BLOCKED_AWAITS_RUNNER,
    sql.COL_BLOCKED_RUNNER_OUTCOME,
    sql.COL_BLOCKED_RUNNER_CODE,
    sql.COL_BLOCKED_RUNNER_REASON,
)
OLD_COLUMNS = tuple(
    column for column in sql.BLOCKED_STATE_COLUMNS if column not in NEW_COLUMNS
)


def _stage_version_eleven_store(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        migrate(connection, expected_version=PRIOR_SCHEMA_VERSION)
        connection.execute(
            LEGACY_INSERT_NODE,
            ("n-1", PROJECT, None, "slice", NodeStatus.BLOCKED_ON_HUMAN.value, "n-1")
            + ("cf-old", None, "old-slice", None)
            + (None,) * 3
            + (STAGED_AT, STAGED_AT),
        )
        connection.execute(
            sql.INSERT_BLOCKED_STATE,
            ("b-done", "n-1", "human", "earlier", STAGED_AT, STAGED_AT),
        )
        connection.execute(
            LEGACY_FILL_RESOLUTION_SLOT,
            ("pm", "done by hand", STAGED_AT, STAGED_AT, "n-1"),
        )
        # One open block per node: the second is inserted after the first resolves.
        connection.execute(
            sql.INSERT_BLOCKED_STATE,
            ("b-open", "n-1", "human", "waiting", STAGED_AT, STAGED_AT),
        )
        connection.commit()


def _old_rows(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
    return connection.execute(
        f"SELECT {', '.join(OLD_COLUMNS)} FROM {sql.TABLE_BLOCKED_STATES} ORDER BY id"
    ).fetchall()


def test_the_expected_version_includes_the_decisions() -> None:
    assert EXPECTED_SCHEMA_VERSION >= DECISIONS_SCHEMA_VERSION


def test_upgrade_keeps_old_rows_and_reads_the_new_columns_as_null(
    store_file: Path,
) -> None:
    _stage_version_eleven_store(store_file)
    with sqlite3.connect(store_file) as connection:
        before = _old_rows(connection)
        assert (
            migrate(connection, expected_version=DECISIONS_SCHEMA_VERSION)
            == DECISIONS_SCHEMA_VERSION
        )
        after = _old_rows(connection)
        rows = connection.execute(
            f"SELECT {', '.join(sql.BLOCKED_STATE_COLUMNS)} "
            f"FROM {sql.TABLE_BLOCKED_STATES} ORDER BY id"
        ).fetchall()
        version = read_schema_version(connection)

    assert len(before) == 2
    assert after == before
    assert version == DECISIONS_SCHEMA_VERSION
    assert all(value is None for row in rows for value in row[len(OLD_COLUMNS) :])
    states = [map_blocked_state(row) for row in rows]
    assert [state.awaits_runner for state in states] == [False, False]
    assert [state.runner_outcome for state in states] == [None, None]
    assert [state.is_resolved for state in states] == [True, False]


def test_the_new_columns_follow_the_old_ones_and_exist(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        info = connection.execute(
            f"PRAGMA table_info({sql.TABLE_BLOCKED_STATES})"
        ).fetchall()
    assert set(sql.BLOCKED_STATE_COLUMNS) == {str(row[1]) for row in info}
    assert sql.BLOCKED_STATE_COLUMNS[-len(NEW_COLUMNS) :] == NEW_COLUMNS


def test_the_partial_index_exists_on_the_flagged_rows(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        found = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
            (sql.INDEX_BLOCKED_AWAITS_RUNNER,),
        ).fetchone()
    assert found is not None
    assert "awaits_runner = 1" in found[0]


def _row(**overrides: object) -> tuple[object, ...]:
    values: dict[str, object] = {
        sql.COL_BLOCKED_ID: "b",
        sql.COL_BLOCKED_NODE_ID: "n",
        sql.COL_BLOCKED_KIND: "human",
        sql.COL_BLOCKED_CONTEXT: "ctx",
        sql.COL_BLOCKED_RESOLVED_BY: "pm",
        sql.COL_BLOCKED_RESOLUTION_DETAIL: "why",
        sql.COL_BLOCKED_RESOLVED_AT: STAGED_AT,
        sql.COL_BLOCKED_CREATED_AT: STAGED_AT,
        sql.COL_BLOCKED_UPDATED_AT: STAGED_AT,
    }
    values.update({column: None for column in NEW_COLUMNS})
    values.update(overrides)
    return tuple(values[column] for column in sql.BLOCKED_STATE_COLUMNS)


def test_each_new_column_round_trips() -> None:
    state = map_blocked_state(
        _row(
            **{
                sql.COL_BLOCKED_RESOLUTION_DECISION: "retry",
                sql.COL_BLOCKED_RESOLUTION_INSTRUCTIONS: "only the schema",
                sql.COL_BLOCKED_AWAITS_RUNNER: 1,
                sql.COL_BLOCKED_RUNNER_OUTCOME: "rejected",
                sql.COL_BLOCKED_RUNNER_CODE: "not_at_loop",
                sql.COL_BLOCKED_RUNNER_REASON: "not a loop",
            }
        )
    )

    assert state.resolution is not None
    assert state.resolution.decision == "retry"
    assert state.resolution.instructions == "only the schema"
    assert state.awaits_runner is True
    assert state.runner_outcome is ResolutionOutcome.REJECTED
    assert state.runner_code == "not_at_loop"
    assert state.runner_reason == "not a loop"


def test_an_unknown_runner_outcome_is_corruption() -> None:
    with pytest.raises(UnknownVocabularyValueError):
        map_blocked_state(_row(**{sql.COL_BLOCKED_RUNNER_OUTCOME: "maybe"}))
