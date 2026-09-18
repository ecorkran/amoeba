"""Tests for store lifecycle, node CRUD, and the project-isolation guarantee."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from amoeba.store import sql
from amoeba.store.models import (
    CFReference,
    NodeKind,
    NodeNotFoundError,
    NodeStatus,
    SQReference,
    UnknownVocabularyValueError,
)
from amoeba.store.store import Store


def _make_node(store: Store, project_id: str = "demo", title: str = "a slice") -> str:
    return store.create_node(project_id=project_id, kind=NodeKind.SLICE, title=title).id


def test_open_creates_and_migrates(store_file: Path) -> None:
    """Opening a fresh path creates the file and brings it to the schema."""
    assert not store_file.exists()

    with Store.open(store_file) as store:
        assert store.path == store_file
        assert store.runnable("demo") == []

    assert store_file.exists()


def test_open_creates_missing_parent_directories(tmp_path: Path) -> None:
    """The open path creates parent directories; resolution never does."""
    nested = tmp_path / "a" / "b" / "store.sqlite3"

    with Store.open(nested) as store:
        assert store.path == nested

    assert nested.exists()


def test_open_requires_a_path_or_project_id() -> None:
    """Opening with neither argument raises rather than guessing a location."""
    with pytest.raises(ValueError, match="path or a project_id"):
        Store.open()


def test_context_manager_releases_on_normal_exit(store_file: Path) -> None:
    """The context-manager form closes the connection on normal exit."""
    store = Store.open(store_file)

    with store:
        _make_node(store)

    with pytest.raises(sqlite3.ProgrammingError):
        store.runnable("demo")


def test_context_manager_releases_on_exception_exit(store_file: Path) -> None:
    """The context-manager form closes the connection on exception exit too."""
    store = Store.open(store_file)

    with pytest.raises(RuntimeError):  # noqa: PT012 - the raise is the subject
        with store:
            _make_node(store)
            raise RuntimeError("boom")

    with pytest.raises(sqlite3.ProgrammingError):
        store.runnable("demo")


def test_create_read_round_trip(store_file: Path) -> None:
    """A created node reads back with every attribute intact."""
    with Store.open(store_file) as store:
        created = store.create_node(
            project_id="demo",
            kind=NodeKind.INITIATIVE,
            title="substrate",
            cf=CFReference(project="amoeba", phase="6"),
            sq=SQReference(run_id="run-20260917-store-abcd1234"),
        )

        fetched = store.get_node(created.id)

        assert fetched is not None
        assert fetched.title == "substrate"
        assert fetched.kind is NodeKind.INITIATIVE
        assert fetched.status is NodeStatus.RUNNABLE
        assert fetched.cf.project == "amoeba"
        assert fetched.sq.run_id == "run-20260917-store-abcd1234"
        assert fetched.created_at is not None


def test_get_unknown_node_returns_none(store_file: Path) -> None:
    """An unknown id reads as None — absence is not an error."""
    with Store.open(store_file) as store:
        assert store.get_node("no-such-node") is None


def test_children_of_lists_direct_children(store_file: Path) -> None:
    """Children are listed by parent, and grandchildren are not included."""
    with Store.open(store_file) as store:
        root = store.create_node(
            project_id="demo", kind=NodeKind.INITIATIVE, title="root"
        )
        child = store.create_node(
            project_id="demo",
            parent_id=root.id,
            kind=NodeKind.SLICE,
            title="child",
        )
        store.create_node(
            project_id="demo",
            parent_id=child.id,
            kind=NodeKind.GATE,
            title="grandchild",
        )

        titles = [node.title for node in store.children_of(root.id)]

        assert titles == ["child"]


def test_create_under_unknown_parent_raises(store_file: Path) -> None:
    """A dangling parent reference raises rather than creating an orphan."""
    with Store.open(store_file) as store:
        with pytest.raises(NodeNotFoundError):
            store.create_node(
                project_id="demo",
                parent_id="no-such-node",
                kind=NodeKind.SLICE,
                title="orphan",
            )


def test_update_status_round_trips(store_file: Path) -> None:
    """A status update is visible on the next read."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)

        updated = store.update_node_status(node_id, NodeStatus.IN_PROGRESS)

        assert updated.status is NodeStatus.IN_PROGRESS
        fetched = store.get_node(node_id)
        assert fetched is not None
        assert fetched.status is NodeStatus.IN_PROGRESS


def test_update_status_of_unknown_node_raises(store_file: Path) -> None:
    """Updating a node that does not exist raises, not a silent no-op."""
    with Store.open(store_file) as store:
        with pytest.raises(NodeNotFoundError):
            store.update_node_status("no-such-node", NodeStatus.DONE)


def test_reference_updates_do_not_change_the_node_id(store_file: Path) -> None:
    """Node identity is stable across reference-field changes."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)

        after_cf = store.update_cf_reference(
            node_id, CFReference(project="amoeba", artifact_path="slices/101.md")
        )
        after_sq = store.update_sq_reference(
            node_id,
            SQReference(run_id="run-20260917-x-abcd1234", reviewed_sha="9fd07d4"),
        )

        assert after_cf.id == node_id
        assert after_sq.id == node_id
        assert after_sq.cf.artifact_path == "slices/101.md"
        assert after_sq.sq.reviewed_sha == "9fd07d4"


def test_references_are_stored_opaquely(store_file: Path) -> None:
    """Reference values are stored verbatim — the store never parses them."""
    unparsed = "not-a-run-id-shaped-value/../weird"

    with Store.open(store_file) as store:
        node_id = _make_node(store)
        updated = store.update_sq_reference(node_id, SQReference(run_id=unparsed))

        assert updated.sq.run_id == unparsed


def test_status_outside_the_vocabulary_raises_on_write(store_file: Path) -> None:
    """A status string outside the vocabulary cannot be written."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)

        with pytest.raises(ValueError):
            store.update_node_status(node_id, NodeStatus("not_a_status"))


def test_unmappable_row_raises_on_read(store_file: Path) -> None:
    """A row carrying an out-of-vocabulary status raises when read.

    Written directly through SQL to bypass the write-side validation: this is
    the read side of the guarantee. The caller must never receive a
    partially-populated object built around a defaulted status.
    """
    with Store.open(store_file) as store:
        node_id = _make_node(store)

        with sqlite3.connect(store_file) as raw:
            raw.execute(
                f"UPDATE {sql.TABLE_NODES} SET {sql.COL_NODE_STATUS} = ? "  # noqa: S608
                f"WHERE {sql.COL_NODE_ID} = ?",
                ("not_a_status", node_id),
            )

        with pytest.raises(UnknownVocabularyValueError, match="not_a_status"):
            store.get_node(node_id)


def test_unmappable_row_raises_in_list_queries(store_file: Path) -> None:
    """The same guarantee holds for list reads, not only single-node reads."""
    with Store.open(store_file) as store:
        node_id = _make_node(store)

        with sqlite3.connect(store_file) as raw:
            raw.execute(
                f"UPDATE {sql.TABLE_NODES} SET {sql.COL_NODE_KIND} = ? "  # noqa: S608
                f"WHERE {sql.COL_NODE_ID} = ?",
                ("not_a_kind", node_id),
            )

        with pytest.raises(UnknownVocabularyValueError):
            store.nodes_for_project("demo")


def test_cross_project_isolation(store_file: Path) -> None:
    """Every query for one project returns none of another project's nodes."""
    with Store.open(store_file) as store:
        alpha = _make_node(store, project_id="alpha", title="alpha slice")
        beta = _make_node(store, project_id="beta", title="beta slice")

        alpha_nodes = store.nodes_for_project("alpha")
        beta_nodes = store.nodes_for_project("beta")

        assert [node.id for node in alpha_nodes] == [alpha]
        assert [node.id for node in beta_nodes] == [beta]
        assert [node.id for node in store.runnable("alpha")] == [alpha]
        assert [node.id for node in store.runnable("beta")] == [beta]


def test_empty_project_queries_return_empty_not_error(store_file: Path) -> None:
    """A project with no nodes yields empty results, never an exception."""
    with Store.open(store_file) as store:
        assert store.nodes_for_project("nothing-here") == []
        assert store.runnable("nothing-here") == []
        assert store.blocked("nothing-here") == []
        assert store.children_of("no-such-node") == []


def test_node_ids_are_store_generated_and_unique(store_file: Path) -> None:
    """Ids are generated by the store, not derived from caller coordinates."""
    with Store.open(store_file) as store:
        first = store.create_node(
            project_id="demo",
            kind=NodeKind.SLICE,
            title="same title",
            cf=CFReference(project="amoeba", slice_name="101"),
        )
        second = store.create_node(
            project_id="demo",
            kind=NodeKind.SLICE,
            title="same title",
            cf=CFReference(project="amoeba", slice_name="101"),
        )

        assert first.id != second.id
