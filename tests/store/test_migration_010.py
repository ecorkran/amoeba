"""Migration 010: ``nodes.cf_index`` and the partial unique link index.

A populated version-9 store upgrades intact, and the link key
``(project_id, kind, cf_project, cf_index)`` is unique only where an index is
set.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from amoeba.store import Store, sql
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION, migrate
from amoeba.store.models import (
    CFReference,
    NodeKind,
    NodeStatus,
    StoreIntegrityError,
)

PRIOR_SCHEMA_VERSION = 9
INDEX_SCHEMA_VERSION = 10

PROJECT = "demo"
OTHER_PROJECT = "other"
CF_PROJECT = "cf-a"
STAGED_AT = "2026-10-23T00:00:00+00:00"


def _stage_version_nine_store(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        migrate(connection, expected_version=PRIOR_SCHEMA_VERSION)
        connection.execute(
            sql.INSERT_NODE,
            ("n-1", PROJECT, None, "slice", NodeStatus.RUNNABLE.value, "n-1")
            + ("cf-old", None, "old-slice", None)
            + (None,) * 3
            + (STAGED_AT, STAGED_AT),
        )
        connection.commit()


def _node_rows(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
    columns = ", ".join(
        column for column in sql.NODE_COLUMNS if column != sql.COL_NODE_CF_INDEX
    )
    return connection.execute(f"SELECT {columns} FROM nodes ORDER BY rowid").fetchall()


def _linked(
    store: Store,
    *,
    index: int | None,
    kind: NodeKind = NodeKind.SLICE,
    cf_project: str = CF_PROJECT,
    project_id: str = PROJECT,
) -> None:
    store.create_node(
        project_id=project_id,
        kind=kind,
        title=f"{kind.value}-{index}",
        cf=CFReference(project=cf_project, index=index),
    )


def test_the_expected_version_is_ten() -> None:
    assert EXPECTED_SCHEMA_VERSION == INDEX_SCHEMA_VERSION


def test_upgrade_keeps_old_rows_and_leaves_the_index_null(store_file: Path) -> None:
    _stage_version_nine_store(store_file)
    with sqlite3.connect(store_file) as connection:
        before = _node_rows(connection)
        assert migrate(connection) == INDEX_SCHEMA_VERSION
        after = _node_rows(connection)
        indexes = connection.execute(
            f"SELECT {sql.COL_NODE_CF_INDEX} FROM nodes"
        ).fetchall()

    assert len(before) == 1
    assert after == before
    assert indexes == [(None,)]


def test_every_node_column_exists_in_the_migrated_table(store_file: Path) -> None:
    with sqlite3.connect(store_file) as connection:
        migrate(connection)
        info = connection.execute("PRAGMA table_info(nodes)").fetchall()
    assert set(sql.NODE_COLUMNS) <= {str(row[1]) for row in info}
    assert sql.NODE_COLUMNS[-1] == sql.COL_NODE_CF_INDEX


def test_a_node_round_trips_its_index() -> None:
    with Store.open_temporary() as store:
        created = store.create_node(
            project_id=PROJECT,
            kind=NodeKind.SLICE,
            title="s",
            cf=CFReference(project=CF_PROJECT, slice_name="x", index=123),
        )
        stored = store.get_node(created.id)
    assert created.cf.index == 123
    assert stored is not None
    assert stored.cf == CFReference(project=CF_PROJECT, slice_name="x", index=123)


def test_a_node_without_an_index_reads_back_null() -> None:
    with Store.open_temporary() as store:
        created = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="s")
        stored = store.get_node(created.id)
    assert stored is not None
    assert stored.cf.index is None


def test_update_cf_reference_replaces_the_index() -> None:
    with Store.open_temporary() as store:
        node = store.create_node(
            project_id=PROJECT,
            kind=NodeKind.SLICE,
            title="s",
            cf=CFReference(project=CF_PROJECT, index=1),
        )
        updated = store.update_cf_reference(
            node.id, CFReference(project=CF_PROJECT, index=2)
        )
        cleared = store.update_cf_reference(node.id, CFReference(project=CF_PROJECT))
    assert updated.cf.index == 2
    assert cleared.cf.index is None


def test_a_duplicate_link_is_refused() -> None:
    with Store.open_temporary() as store:
        _linked(store, index=5)
        with pytest.raises(StoreIntegrityError):
            _linked(store, index=5)
        assert len(store.nodes_for_project(PROJECT)) == 1


def test_a_refused_duplicate_leaves_no_node_behind() -> None:
    with Store.open_temporary() as store:
        _linked(store, index=5)
        with pytest.raises(StoreIntegrityError):
            _linked(store, index=5)
        _linked(store, index=6)
        assert len(store.nodes_for_project(PROJECT)) == 2


def test_update_cf_reference_to_a_taken_link_is_refused() -> None:
    with Store.open_temporary() as store:
        _linked(store, index=5)
        node = store.create_node(
            project_id=PROJECT,
            kind=NodeKind.SLICE,
            title="b",
            cf=CFReference(project=CF_PROJECT, index=6),
        )
        with pytest.raises(StoreIntegrityError):
            store.update_cf_reference(node.id, CFReference(project=CF_PROJECT, index=5))


@pytest.mark.parametrize(
    ("kind", "cf_project", "project_id"),
    [
        (NodeKind.INITIATIVE, CF_PROJECT, PROJECT),
        (NodeKind.SLICE, "cf-b", PROJECT),
        (NodeKind.SLICE, CF_PROJECT, OTHER_PROJECT),
    ],
    ids=["other-kind", "other-cf-project", "other-amoeba-project"],
)
def test_the_same_index_is_allowed_when_another_key_part_differs(
    kind: NodeKind, cf_project: str, project_id: str
) -> None:
    with Store.open_temporary() as store:
        _linked(store, index=5)
        _linked(store, index=5, kind=kind, cf_project=cf_project, project_id=project_id)


def test_null_indexes_never_collide() -> None:
    with Store.open_temporary() as store:
        _linked(store, index=None)
        _linked(store, index=None)
        assert len(store.nodes_for_project(PROJECT)) == 2
