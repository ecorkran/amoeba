"""``Store``: opening, transactions, the typed errors (slice 222, D2)."""

from __future__ import annotations

import os
import sqlite3
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fault_injection import InjectedFailureError, fail_on_statement

from amoeba.store import sql
from amoeba.store.errors import (
    StoreBusyError,
    StoreCorruptError,
    StorePermissionError,
    StoreSchemaError,
)
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store, Transaction
from store.seed import insert_member, insert_program

NOW = datetime(2026, 11, 9, tzinfo=UTC)
SHORT_TIMEOUT_SECONDS = 0.2


def _program(transaction: Transaction, program_id: str = "demo") -> None:
    insert_program(
        transaction,
        program_id=program_id,
        concept_member=None,
        concept_path=None,
        registered_at=NOW,
        updated_at=NOW,
    )


def _version(path: Path) -> int:
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT version FROM schema_meta").fetchone()
    return int(row[0])


def test_open_creates_the_directory_and_the_store(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "deeper" / "amoeba.sqlite3"

    with Store.open(path):
        pass

    assert path.exists()
    assert _version(path) == EXPECTED_SCHEMA_VERSION


def test_the_busy_timeout_is_defined_once() -> None:
    assert BUSY_TIMEOUT_SECONDS == 5.0


def test_reopen_applies_nothing(tmp_path: Path) -> None:
    path = tmp_path / "amoeba.sqlite3"
    with Store.open(path) as store, store.write() as transaction:
        _program(transaction)

    with Store.open(path) as store, store.read() as transaction:
        rows = transaction.execute("SELECT program_id FROM programs").fetchall()
        markers = transaction.execute("SELECT count(*) FROM pm_marker").fetchone()

    assert [row[0] for row in rows] == ["demo"]
    assert markers[0] == 1
    assert _version(path) == EXPECTED_SCHEMA_VERSION


def test_a_store_stamped_higher_is_refused_and_untouched(tmp_path: Path) -> None:
    path = tmp_path / "amoeba.sqlite3"
    Store.open(path).close()
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE schema_meta SET version = ?", (99,))
    connection.close()
    before = path.read_bytes()

    with pytest.raises(StoreSchemaError, match="99"):
        Store.open(path)

    assert path.read_bytes() == before


def test_a_second_writer_past_the_timeout_gets_store_busy(tmp_path: Path) -> None:
    path = tmp_path / "amoeba.sqlite3"
    holder = Store.open(path)
    waiter = Store.open(path, busy_timeout_seconds=SHORT_TIMEOUT_SECONDS)

    with holder.write():
        with pytest.raises(StoreBusyError) as busy, waiter.write():
            pass
        # A third process opening while the lock is held waits, then fails the same way.
        with pytest.raises(StoreBusyError):
            Store.open(path, busy_timeout_seconds=SHORT_TIMEOUT_SECONDS)

    assert str(path) in str(busy.value)
    assert str(SHORT_TIMEOUT_SECONDS) in str(busy.value)
    holder.close()
    waiter.close()


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unwritable_directory_is_a_permission_error(tmp_path: Path) -> None:
    directory = tmp_path / "locked"
    directory.mkdir()
    directory.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(StorePermissionError):
            Store.open(directory / "amoeba.sqlite3")
    finally:
        directory.chmod(stat.S_IRWXU)


def test_a_file_that_is_not_a_database_is_a_corrupt_error(tmp_path: Path) -> None:
    path = tmp_path / "amoeba.sqlite3"
    path.write_bytes(b"this is not a sqlite database\n" * 200)

    with pytest.raises(StoreCorruptError):
        Store.open(path)


def test_a_failed_write_block_rolls_back(tmp_path: Path) -> None:
    with Store.open(tmp_path / "amoeba.sqlite3") as store:
        with pytest.raises(ValueError, match="boom"), store.write() as transaction:
            _program(transaction)
            raise ValueError("boom")

        with store.read() as transaction:
            count = transaction.execute("SELECT count(*) FROM programs").fetchone()

    assert count[0] == 0


def test_a_fault_on_the_second_insert_leaves_no_program_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Store.open(tmp_path / "amoeba.sqlite3") as store:
        with pytest.raises(InjectedFailureError), store.write() as transaction:
            fail_on_statement(monkeypatch, transaction, sql.INSERT_MEMBER)
            _program(transaction)
            insert_member(
                transaction,
                project_id="m1",
                program_id="demo",
                rules_paths=("CLAUDE.md",),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=NOW,
                updated_at=NOW,
            )

        with store.read() as transaction:
            programs = transaction.execute("SELECT count(*) FROM programs").fetchone()

    assert programs[0] == 0
