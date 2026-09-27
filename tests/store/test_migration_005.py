"""Migration 005: a populated version-4 store upgrades intact; bad rows never map.

The fixture is staged as slice 103 code would have left it — nodes, a journal
entry, an inbox submission, and a message — by migrating to version 4 and
writing through the store's own statements. Then it is upgraded to 5.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.store import sql, sql_evidence, sql_inbox, sql_journal
from amoeba.store.evidence_models import (
    FindingInput,
    FindingSeverity,
    Provenance,
    RecordSource,
    ReviewVerdict,
    VerdictDerivation,
    VerdictInput,
)
from amoeba.store.mapping_evidence import (
    map_observation,
    map_verdict,
    observation_parameters,
    verdict_parameters,
)
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION, migrate
from amoeba.store.models import NodeStatus, UnknownVocabularyValueError

INBOX_SCHEMA_VERSION = 4
EVIDENCE_SCHEMA_VERSION = 5

PROJECT = "demo"
STAGED_AT = "2026-09-26T00:00:00+00:00"


def _insert_node(connection: sqlite3.Connection, node_id: str) -> None:
    connection.execute(
        sql.INSERT_NODE,
        (node_id, PROJECT, None, "slice", NodeStatus.RUNNABLE.value, node_id)
        + (None,) * 7
        + (STAGED_AT, STAGED_AT),
    )


def _stage_version_four_store(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        migrate(connection, expected_version=INBOX_SCHEMA_VERSION)
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
        connection.commit()


def _rows(connection: sqlite3.Connection, table: str) -> list[tuple[object, ...]]:
    return connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()


def _schema_objects(connection: sqlite3.Connection, kind: str) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = ?", (kind,)
    ).fetchall()
    return {str(row[0]) for row in rows}


_PRIOR_TABLES = (
    sql.TABLE_NODES,
    sql_journal.TABLE_COMMAND_JOURNAL,
    sql_inbox.TABLE_INBOX_SUBMISSIONS,
    sql_inbox.TABLE_MESSAGES,
)


def test_version_five_is_the_expected_version() -> None:
    assert EXPECTED_SCHEMA_VERSION == EVIDENCE_SCHEMA_VERSION


def test_upgrade_keeps_every_prior_row(store_file: Path) -> None:
    _stage_version_four_store(store_file)
    with sqlite3.connect(store_file) as connection:
        before = {table: _rows(connection, table) for table in _PRIOR_TABLES}
        assert migrate(connection) == EVIDENCE_SCHEMA_VERSION
        after = {table: _rows(connection, table) for table in _PRIOR_TABLES}

    assert [len(before[table]) for table in _PRIOR_TABLES] == [2, 1, 1, 1]
    assert after == before


def test_fresh_store_has_both_tables_and_all_indexes(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        assert {
            sql_evidence.TABLE_VERDICTS,
            sql_evidence.TABLE_FINDING_OBSERVATIONS,
        } <= _schema_objects(connection, "table")
        indexes = _schema_objects(connection, "index")

    assert {
        sql_evidence.INDEX_VERDICTS_PREVIOUS_ROUND,
        sql_evidence.INDEX_FINDING_OBSERVATIONS_IDENTITY,
    } <= indexes
    # The UNIQUE verdict id is SQLite's automatic index on verdicts.
    assert any(name.startswith("sqlite_autoindex_verdicts") for name in indexes)


def test_columns_match_the_single_definition_site(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        for table, expected in (
            (sql_evidence.TABLE_VERDICTS, sql_evidence.VERDICT_COLUMNS),
            (sql_evidence.TABLE_FINDING_OBSERVATIONS, sql_evidence.OBSERVATION_COLUMNS),
        ):
            info = connection.execute(f"PRAGMA table_info({table})").fetchall()
            assert tuple(str(row[1]) for row in info) == expected, table


def test_recorded_seq_is_autoincrement(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        ddl = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (sql_evidence.TABLE_VERDICTS,),
        ).fetchone()
    column = sql_evidence.COL_VERDICT_RECORDED_SEQ
    assert f"{column} integer primary key autoincrement" in str(ddl[0]).lower()


_VERDICT = VerdictInput(
    id="v-1",
    node_id="n-1",
    verdict=ReviewVerdict.CONCERNS,
    derivation=VerdictDerivation.STATED,
    fallback_used=None,
    findings_parsed=True,
    provider_failure=False,
    review_type="tasks",
    model="m",
    findings=(FindingInput(severity=FindingSeverity.CONCERN, summary="s"),),
    provenance=Provenance(
        upstream="squadron",
        upstream_version="0.14.0",
        source=RecordSource.ARTIFACT_FRONTMATTER,
    ),
)


@pytest.fixture
def evidence_connection(store_file: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(store_file)
    migrate(connection)
    _insert_node(connection, "n-1")
    connection.execute(
        sql_evidence.INSERT_VERDICT, verdict_parameters(_VERDICT, PROJECT, STAGED_AT)
    )
    connection.execute(
        sql_evidence.INSERT_OBSERVATION,
        observation_parameters(_VERDICT.id, 0, _VERDICT.findings[0]),
    )
    yield connection
    connection.close()


def _verdict_row(connection: sqlite3.Connection) -> tuple[object, ...]:
    return connection.execute(sql_evidence.SELECT_VERDICT_BY_ID, ("v-1",)).fetchone()


def test_a_valid_row_maps(evidence_connection: sqlite3.Connection) -> None:
    record = map_verdict(_verdict_row(evidence_connection), _VERDICT.findings)
    assert record.derivation is VerdictDerivation.STATED
    rows = evidence_connection.execute(sql_evidence.SELECT_OBSERVATIONS, ("v-1",))
    assert map_observation(rows.fetchone()).severity is FindingSeverity.CONCERN


@pytest.mark.parametrize(
    "column", [sql_evidence.COL_VERDICT_DERIVATION, sql_evidence.COL_VERDICT_VERDICT]
)
def test_an_unknown_verdict_enum_raises(
    evidence_connection: sqlite3.Connection, column: str
) -> None:
    evidence_connection.execute(
        f"UPDATE {sql_evidence.TABLE_VERDICTS} SET {column} = 'guessed'"
    )
    with pytest.raises(UnknownVocabularyValueError, match=column):
        map_verdict(_verdict_row(evidence_connection), ())


def test_an_unknown_severity_raises(evidence_connection: sqlite3.Connection) -> None:
    column = sql_evidence.COL_OBSERVATION_SEVERITY
    evidence_connection.execute(
        f"UPDATE {sql_evidence.TABLE_FINDING_OBSERVATIONS} SET {column} = 'warning'"
    )
    row = evidence_connection.execute(
        sql_evidence.SELECT_OBSERVATIONS, ("v-1",)
    ).fetchone()
    with pytest.raises(UnknownVocabularyValueError, match=column):
        map_observation(row)
