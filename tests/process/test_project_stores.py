"""Atomic runtime creation of a project store by ``ProjectStores.open_project``.

A submitter polls for its new project's store read-only, and a read-only open
never migrates, so the store must appear at its final path only once complete.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba.process.project_stores import ProjectStores
from amoeba.process.supervisor import discover_project_ids, store_path_for
from amoeba.store import NodeKind, Store
from amoeba.store.paths import STORE_CREATING_SUFFIX

PROJECT = "fresh"


def _building_path(final: Path) -> Path:
    return final.with_name(final.name + STORE_CREATING_SUFFIX)


def test_a_new_store_is_complete_and_leaves_nothing_behind(tmp_path: Path) -> None:
    stores = ProjectStores(tmp_path)
    try:
        stores.open_project(PROJECT)
    finally:
        stores.close_all()

    final = store_path_for(tmp_path, PROJECT)
    # Listed before the read-only open, which leaves its own WAL files.
    assert sorted(path.name for path in tmp_path.iterdir()) == [final.name]
    # Opening read-only at all proves the file is at the expected schema.
    Store.open_read_only(final).close()


def test_the_final_path_is_absent_until_migration_is_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    final = store_path_for(tmp_path, PROJECT)
    final_existed_during_build: list[bool] = []
    real_open = Store.open

    def recording_open(path: Path | None = None, **kwargs: object) -> Store:
        if path == _building_path(final):
            final_existed_during_build.append(final.exists())
        return real_open(path, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Store, "open", recording_open)
    stores = ProjectStores(tmp_path)
    try:
        stores.open_project(PROJECT)
    finally:
        stores.close_all()

    assert final_existed_during_build == [False]
    assert final.exists()


def test_a_leftover_from_a_crashed_creation_is_replaced(tmp_path: Path) -> None:
    final = store_path_for(tmp_path, PROJECT)
    _building_path(final).write_bytes(b"not a database: a crash mid-creation")
    assert discover_project_ids(tmp_path) == []

    stores = ProjectStores(tmp_path)
    try:
        stores.open_project(PROJECT)
    finally:
        stores.close_all()

    Store.open_read_only(final).close()
    assert not _building_path(final).exists()
    assert discover_project_ids(tmp_path) == [PROJECT]


def test_an_existing_store_is_opened_not_rebuilt(tmp_path: Path) -> None:
    stores = ProjectStores(tmp_path)
    try:
        stores.open_project(PROJECT).create_node(
            project_id=PROJECT, kind=NodeKind.SLICE, title="kept"
        )
    finally:
        stores.close_all()

    reopened = ProjectStores(tmp_path)
    try:
        store = reopened.open_project(PROJECT)
        assert [node.title for node in store.nodes_for_project(PROJECT)] == ["kept"]
    finally:
        reopened.close_all()
