"""The program store's read-write holder in ``ProjectStores``."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from amoeba.process.errors import StartupFailedError
from amoeba.process.project_stores import ProjectStores
from amoeba.store import ProgramStore
from amoeba.store.paths import STORE_CREATING_SUFFIX, program_dir, program_store_path


def _building_path(final: Path) -> Path:
    return final.with_name(final.name + STORE_CREATING_SUFFIX)


def test_with_no_file_the_program_store_is_none_after_start(tmp_path: Path) -> None:
    stores = ProjectStores(tmp_path)

    stores.open_program_store()

    assert stores.program_store is None
    assert not program_dir(tmp_path).exists()


def test_creation_is_complete_and_leaves_no_creating_file_or_wal(
    tmp_path: Path,
) -> None:
    stores = ProjectStores(tmp_path)
    try:
        created = stores.ensure_program_store()
        assert stores.program_store is created
    finally:
        stores.close_all()

    final = program_store_path(tmp_path)
    # Listed before the read-only open, which leaves its own WAL files.
    assert sorted(path.name for path in program_dir(tmp_path).iterdir()) == [final.name]
    ProgramStore.open_read_only(final).close()


def test_ensure_is_idempotent(tmp_path: Path) -> None:
    stores = ProjectStores(tmp_path)
    try:
        assert stores.ensure_program_store() is stores.ensure_program_store()
    finally:
        stores.close_all()


def test_the_final_path_is_absent_until_migration_is_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    final = program_store_path(tmp_path)
    existed_during_build: list[bool] = []
    real_open = ProgramStore.open

    def recording_open(path: Path, **kwargs: float) -> ProgramStore:
        if path == _building_path(final):
            existed_during_build.append(final.exists())
        return real_open(path, **kwargs)

    monkeypatch.setattr(ProgramStore, "open", recording_open)
    stores = ProjectStores(tmp_path)
    try:
        stores.ensure_program_store()
    finally:
        stores.close_all()

    assert existed_during_build == [False]
    assert final.exists()


def test_a_leftover_creating_file_is_replaced(tmp_path: Path) -> None:
    final = program_store_path(tmp_path)
    final.parent.mkdir()
    _building_path(final).write_bytes(b"not a database: a crash mid-creation")

    stores = ProjectStores(tmp_path)
    try:
        stores.ensure_program_store()
    finally:
        stores.close_all()

    ProgramStore.open_read_only(final).close()
    assert not _building_path(final).exists()


def test_start_opens_an_existing_program_store(tmp_path: Path) -> None:
    ProgramStore.open(program_store_path(tmp_path)).close()
    stores = ProjectStores(tmp_path)
    try:
        stores.open_program_store()
        assert stores.program_store is not None
    finally:
        stores.close_all()


def test_a_junk_program_store_at_start_raises_startup_failed(tmp_path: Path) -> None:
    final = program_store_path(tmp_path)
    final.parent.mkdir()
    final.write_bytes(b"junk, not a database" * 20)
    stores = ProjectStores(tmp_path)

    with pytest.raises(StartupFailedError, match="program store"):
        stores.open_program_store()


def test_close_all_closes_the_program_store(tmp_path: Path) -> None:
    stores = ProjectStores(tmp_path)
    held = stores.ensure_program_store()

    stores.close_all()

    assert stores.program_store is None
    with pytest.raises(sqlite3.ProgrammingError):
        held.programs()
