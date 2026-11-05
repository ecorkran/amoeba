"""ProgramStore: opens and reads, mirroring tests/test_read_only_open.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from amoeba.store import sql
from amoeba.store.inbox_models import SubmissionOutcome
from amoeba.store.migrations import (
    EXPECTED_PROGRAM_SCHEMA_VERSION,
    read_schema_version,
)
from amoeba.store.models import (
    StoreCorruptError,
    StorePermissionError,
    StoreSchemaError,
)
from amoeba.store.program_models import ConsumptionMode, ProgramSubmissionKind
from amoeba.store.program_store import ProgramStore

T1 = "2026-11-05T01:00:00+00:00"
T2 = "2026-11-05T02:00:00+00:00"
INSERT_PROGRAM = "INSERT INTO programs VALUES (?, ?, ?, ?, ?)"
INSERT_MEMBER = "INSERT INTO program_members VALUES (?, ?, ?, ?, ?, ?)"
INSERT_OVERRIDE = "INSERT INTO consumption_overrides VALUES (?, ?, ?, ?)"
INSERT_SUBMISSION = "INSERT INTO program_submissions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"


@pytest.fixture
def store_file(tmp_path: Path) -> Path:
    return tmp_path / "programs" / "programs.sqlite3"


def _seed(path: Path) -> None:
    """One program with two members and one override, written with plain SQL."""
    with ProgramStore.open(path):
        pass
    with sqlite3.connect(path) as connection:
        connection.execute(INSERT_PROGRAM, ("demo", "data", "docs/c.md", T1, T1))
        connection.execute(INSERT_MEMBER, ("demo", "data", 790, "from_source", T1, T1))
        connection.execute(
            INSERT_MEMBER, ("demo", "engine", 791, "from_release", T1, T2)
        )
        connection.execute(INSERT_OVERRIDE, ("demo", "data", "engine", "from_release"))


def test_open_creates_the_file_and_stamps_version_one(store_file: Path) -> None:
    with ProgramStore.open(store_file) as store:
        assert store.path == store_file
        assert store.programs() == []

    with sqlite3.connect(store_file) as connection:
        assert read_schema_version(connection) == EXPECTED_PROGRAM_SCHEMA_VERSION == 1


def test_reopen_is_idempotent(store_file: Path) -> None:
    _seed(store_file)
    with ProgramStore.open(store_file) as store:
        assert [program.program_id for program in store.programs()] == ["demo"]


def test_read_only_open_of_a_missing_file_creates_nothing(store_file: Path) -> None:
    with pytest.raises(StorePermissionError):
        ProgramStore.open_read_only(store_file)

    assert not store_file.exists()
    assert not store_file.parent.exists()


def test_read_only_open_of_a_corrupt_file_raises(store_file: Path) -> None:
    store_file.parent.mkdir()
    store_file.write_bytes(b"junk, not a database" * 20)

    with pytest.raises(StoreCorruptError):
        ProgramStore.open_read_only(store_file)


@pytest.mark.parametrize("delta", [1, -1])
def test_read_only_open_at_another_version_raises_and_changes_nothing(
    store_file: Path, delta: int
) -> None:
    _seed(store_file)
    with sqlite3.connect(store_file) as connection:
        connection.execute(
            sql.UPSERT_SCHEMA_VERSION,
            (sql.SCHEMA_META_ROW_ID, EXPECTED_PROGRAM_SCHEMA_VERSION + delta),
        )
    before = store_file.read_bytes()

    with pytest.raises(StoreSchemaError):
        ProgramStore.open_read_only(store_file)

    assert store_file.read_bytes() == before


def test_a_write_through_the_read_only_handle_raises(store_file: Path) -> None:
    _seed(store_file)
    with (
        ProgramStore.open_read_only(store_file) as store,
        pytest.raises(sqlite3.OperationalError, match="readonly"),
    ):
        store._connection.execute(  # pyright: ignore[reportPrivateUsage]
            INSERT_PROGRAM, ("other", "x", "y.md", T1, T1)
        )


def test_program_of_a_member_a_non_member_and_an_empty_store(store_file: Path) -> None:
    with ProgramStore.open(store_file) as empty:
        assert empty.program_of("data") is None

    _seed(store_file)
    with ProgramStore.open_read_only(store_file) as store:
        member_program = store.program_of("engine")
        assert member_program is not None
        assert member_program.program_id == "demo"
        assert member_program.concept_member == "data"
        assert store.program_of("stranger") is None
        assert store.program("demo") == member_program
        assert store.program("nope") is None


def test_members_carry_their_overrides(store_file: Path) -> None:
    _seed(store_file)
    with ProgramStore.open_read_only(store_file) as store:
        data, engine = store.members("demo")
        assert store.members("nope") == []

    assert (data.project_id, data.requests_initiative) == ("data", 790)
    assert data.consumed is ConsumptionMode.FROM_SOURCE
    assert dict(data.overrides) == {"engine": ConsumptionMode.FROM_RELEASE}
    assert engine.consumed is ConsumptionMode.FROM_RELEASE
    assert dict(engine.overrides) == {}
    assert engine.updated_at > engine.registered_at


def test_submissions_come_back_in_applied_order(store_file: Path) -> None:
    _seed(store_file)
    with sqlite3.connect(store_file) as connection:
        for seq, submission_id, outcome, reason in (
            (2, "second", "rejected", "unknown_program: nope"),
            (1, "first", "applied", None),
        ):
            connection.execute(
                INSERT_SUBMISSION,
                (
                    submission_id,
                    "register_program",
                    "operator",
                    T1,
                    seq,
                    T2,
                    outcome,
                    reason,
                    '{"program_id": "demo"}',
                ),
            )

    with ProgramStore.open_read_only(store_file) as store:
        records = store.submissions()
        first = store.submission("first")

    assert [record.id for record in records] == ["first", "second"]
    assert first is not None
    assert first.kind is ProgramSubmissionKind.REGISTER_PROGRAM
    assert first.outcome is SubmissionOutcome.APPLIED
    assert dict(first.payload) == {"program_id": "demo"}
    assert records[1].reason == "unknown_program: nope"
    assert store_file.exists()
