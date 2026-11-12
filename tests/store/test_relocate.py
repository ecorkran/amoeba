"""``copy_store`` and ``verify_copy`` (slice 228, D2 steps 2 and 3)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

import pytest

from amoeba.store import sql
from amoeba.store.errors import StoreError, StoreRelocateError
from amoeba.store.relocate import copy_store, verify_copy
from store.relocate_support import seed_store

SELECT_ANSWERS = "SELECT run_id, answer, resume_log FROM answers ORDER BY seq"
SELECT_TABLE_ROWS = "SELECT name FROM sqlite_master WHERE type = 'table'"


def _rows(path: Path, statement: str) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(path)) as connection:
        return [tuple(row) for row in connection.execute(statement)]


def _all_tables(path: Path) -> dict[str, list[tuple[object, ...]]]:
    names = [str(name) for (name,) in _rows(path, sql.SELECT_USER_TABLE_NAMES)]
    return {name: _rows(path, f'SELECT * FROM "{name}"') for name in names}


@pytest.fixture
def legacy(tmp_path: Path) -> Path:
    return tmp_path / "legacy"


@pytest.fixture
def target(tmp_path: Path) -> Path:
    directory = tmp_path / "state"
    directory.mkdir()
    return directory / "amoeba.sqlite3.moving"


def test_a_copy_has_every_row_and_only_matching_resume_logs_are_rewritten(
    legacy: Path, target: Path, tmp_path: Path
) -> None:
    old = seed_store(legacy)
    before = _all_tables(old)
    new_prefix = str(tmp_path / "state")

    copy_store(old, target, str(legacy), new_prefix)

    after = _all_tables(target)
    assert after.keys() == before.keys()
    assert {t: rows for t, rows in after.items() if t != "answers"} == {
        t: rows for t, rows in before.items() if t != "answers"
    }
    assert _rows(target, SELECT_ANSWERS) == [
        ("run-a", "yes", f"{new_prefix}/logs/resume/run-a/1.log"),
        ("run-b", "yes", "/elsewhere/logs/run-b.log"),
        ("run-c", "yes", None),
    ]
    assert _rows(old, SELECT_ANSWERS)[0][2] == f"{legacy}/logs/resume/run-a/1.log"


def test_a_sibling_directory_sharing_the_prefix_is_not_rewritten(
    legacy: Path, target: Path, tmp_path: Path
) -> None:
    old = seed_store(legacy)
    sibling = f"{legacy}-other/logs/run-c.log"
    with closing(sqlite3.connect(old)) as connection:
        connection.execute(
            "UPDATE answers SET resume_log = ? WHERE run_id = 'run-c'", (sibling,)
        )
        connection.commit()

    copy_store(old, target, str(legacy), str(tmp_path / "state"))

    assert _rows(target, SELECT_ANSWERS)[2][2] == sibling


def test_the_source_is_not_modified_by_a_copy(
    legacy: Path, target: Path, tmp_path: Path
) -> None:
    old = seed_store(legacy)
    before = _all_tables(old)

    copy_store(old, target, str(legacy), str(tmp_path / "state"))

    assert _all_tables(old) == before


def _doctor_missing_row(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("DELETE FROM answers WHERE run_id = 'run-c'")
        connection.execute("DELETE FROM questions WHERE run_id = 'run-c'")
        connection.commit()


def _doctor_version(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("UPDATE schema_meta SET version = version + 1")
        connection.commit()


def _doctor_max_seq(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("UPDATE answers SET seq = seq + 100 WHERE run_id = 'run-c'")
        connection.commit()


def _doctor_stale_resume_log(path: Path, legacy: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "UPDATE answers SET resume_log = ? WHERE run_id = 'run-c'",
            (f"{legacy}/logs/resume/run-c/1.log",),
        )
        connection.commit()


def _doctor_integrity(path: Path) -> None:
    """Orphan an index's pages: the schema forgets the index, the pages stay."""
    with closing(sqlite3.connect(path, isolation_level=None)) as connection:
        connection.execute("CREATE TABLE junk (x)")
        connection.execute("CREATE INDEX junk_index ON junk (x)")
        connection.execute("INSERT INTO junk VALUES (1), (2), (3)")
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute("DELETE FROM sqlite_master WHERE name = 'junk_index'")
        connection.execute("PRAGMA writable_schema = OFF")


@pytest.mark.parametrize(
    ("doctor", "check"),
    [
        (_doctor_missing_row, "row count of"),
        (_doctor_version, "schema version"),
        (_doctor_max_seq, r"MAX\(answers.seq\)"),
        (_doctor_integrity, "integrity_check"),
    ],
)
def test_verify_copy_names_the_failed_check_and_deletes_the_target(
    legacy: Path,
    target: Path,
    tmp_path: Path,
    doctor: Callable[[Path], None],
    check: str,
) -> None:
    old = seed_store(legacy)
    copy_store(old, target, str(legacy), str(tmp_path / "state"))
    doctor(target)

    with pytest.raises(StoreRelocateError, match=check):
        verify_copy(old, target, str(legacy))

    assert not target.exists()


def test_verify_copy_catches_a_resume_log_still_under_the_old_prefix(
    legacy: Path, target: Path, tmp_path: Path
) -> None:
    old = seed_store(legacy)
    copy_store(old, target, str(legacy), str(tmp_path / "state"))
    _doctor_stale_resume_log(target, legacy)

    with pytest.raises(StoreRelocateError, match="resume_log"):
        verify_copy(old, target, str(legacy))

    assert not target.exists()


def test_a_relocate_error_is_a_store_error() -> None:
    assert issubclass(StoreRelocateError, StoreError)


def test_a_copy_that_raises_oserror_leaves_no_target_and_an_untouched_source(
    legacy: Path, target: Path, tmp_path: Path
) -> None:
    old = seed_store(legacy)
    before = _all_tables(old)

    def fail() -> None:
        raise OSError("disk full")

    with pytest.raises(StoreRelocateError, match="disk full"):
        copy_store(old, target, str(legacy), str(tmp_path / "state"), after_backup=fail)

    assert not target.exists()
    assert _all_tables(old) == before


def test_a_missing_source_raises_and_creates_no_target(
    legacy: Path, target: Path, tmp_path: Path
) -> None:
    with pytest.raises(StoreRelocateError):
        copy_store(
            legacy / "amoeba.sqlite3", target, str(legacy), str(tmp_path / "state")
        )

    assert not target.exists()
    assert not (legacy / "amoeba.sqlite3").exists()
