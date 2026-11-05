"""Program store schema 001: the table set, and each vocabulary pinned to its CHECK."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path

import pytest

from amoeba.store import sql
from amoeba.store.inbox_models import SubmissionOutcome
from amoeba.store.migrations import (
    EXPECTED_PROGRAM_SCHEMA_VERSION,
    PROGRAM_MIGRATIONS_PACKAGE,
    migrate_package,
    read_schema_version,
)
from amoeba.store.models import StoreSchemaError
from amoeba.store.program_models import (
    REQUESTS_INITIATIVE_MAX,
    REQUESTS_INITIATIVE_MIN,
    ConsumptionMode,
)

NOW = "2026-11-05T00:00:00+00:00"
PROGRAM_TABLES = {
    "schema_meta",
    "programs",
    "program_members",
    "consumption_overrides",
    "program_submissions",
}
INSERT_PROGRAM = "INSERT INTO programs VALUES (?, 'm', 'docs/concept.md', ?, ?)"
INSERT_MEMBER = "INSERT INTO program_members VALUES (?, ?, 790, 'from_source', ?, ?)"


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    with sqlite3.connect(tmp_path / "scratch.sqlite3") as scratch:
        scratch.execute(sql.PRAGMA_FOREIGN_KEYS_ON)
        migrate_package(
            scratch,
            package=PROGRAM_MIGRATIONS_PACKAGE,
            expected_version=EXPECTED_PROGRAM_SCHEMA_VERSION,
        )
        yield scratch


def _create_sql(connection: sqlite3.Connection, table: str) -> str:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    assert row is not None
    return str(row[0])


def _check_list(create_sql: str, column: str) -> set[str]:
    """The values of ``CHECK (column IN ('a', 'b'))`` in a CREATE TABLE."""
    match = re.search(rf"CHECK\s*\(\s*{column}\s+IN\s*\(([^)]*)\)\s*\)", create_sql)
    assert match is not None, f"no IN-list CHECK on {column}"
    return set(re.findall(r"'([^']*)'", match.group(1)))


def _values(enum: type[StrEnum]) -> set[str]:
    return {member.value for member in enum}


def test_the_program_store_has_exactly_the_allowed_tables(
    connection: sqlite3.Connection,
) -> None:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    assert {row[0] for row in rows} == PROGRAM_TABLES
    assert read_schema_version(connection) == EXPECTED_PROGRAM_SCHEMA_VERSION == 1


def test_consumption_mode_matches_both_check_constraints(
    connection: sqlite3.Connection,
) -> None:
    for table in ("program_members", "consumption_overrides"):
        assert _check_list(_create_sql(connection, table), "consumed") == _values(
            ConsumptionMode
        )


def test_submission_outcome_matches_its_check_constraint(
    connection: sqlite3.Connection,
) -> None:
    assert _check_list(
        _create_sql(connection, "program_submissions"), "outcome"
    ) == _values(SubmissionOutcome)


def test_the_initiative_range_matches_the_between_bounds(
    connection: sqlite3.Connection,
) -> None:
    match = re.search(
        r"BETWEEN\s+(\d+)\s+AND\s+(\d+)", _create_sql(connection, "program_members")
    )
    assert match is not None
    assert (int(match.group(1)), int(match.group(2))) == (
        REQUESTS_INITIATIVE_MIN,
        REQUESTS_INITIATIVE_MAX,
    )


def test_one_project_cannot_be_a_member_of_two_programs(
    connection: sqlite3.Connection,
) -> None:
    for program_id in ("one", "two"):
        connection.execute(INSERT_PROGRAM, (program_id, NOW, NOW))
    connection.execute(INSERT_MEMBER, ("one", "shared", NOW, NOW))

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        connection.execute(INSERT_MEMBER, ("two", "shared", NOW, NOW))


def test_an_override_cannot_name_its_own_provider(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(INSERT_PROGRAM, ("one", NOW, NOW))
    connection.execute(INSERT_MEMBER, ("one", "solo", NOW, NOW))

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        connection.execute(
            "INSERT INTO consumption_overrides"
            " VALUES ('one', 'solo', 'solo', 'from_release')"
        )


def test_a_newer_stamped_program_store_raises_a_schema_error(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        sql.UPSERT_SCHEMA_VERSION,
        (sql.SCHEMA_META_ROW_ID, EXPECTED_PROGRAM_SCHEMA_VERSION + 1),
    )

    with pytest.raises(StoreSchemaError, match="newer"):
        migrate_package(
            connection,
            package=PROGRAM_MIGRATIONS_PACKAGE,
            expected_version=EXPECTED_PROGRAM_SCHEMA_VERSION,
        )
