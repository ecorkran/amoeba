"""Evidence for the LLD's second technical risk, and the read-only contract.

SQLite needs the ``-shm`` file to read a WAL-mode database, and ``mode=ro``
behaves differently across versions. The LLD requires that this be *measured*
on the project's actual Python and SQLite build before any code depends on the
answer, with the fallback (a read-write handle inspection never writes through)
taken only on evidence.

Measurement recorded 20260921 on this project's build:

    Python  3.13.7
    SQLite  3.50.4   (sqlite3.sqlite_version)

    Writer down, WAL store, mode=ro  ->  reads succeed
    Writer alive in another process  ->  reads succeed
    Write attempted through mode=ro  ->  sqlite3.OperationalError

True ``mode=ro`` therefore works and **the fallback was not taken**. The
sole-writer invariant stands unqualified: inspection holds a genuinely
read-only handle, and the contract documents say so without softening.

The version numbers above are a dated observation of what was measured, not a
requirement or a pin — if a future build behaves differently, these tests fail
and the fallback is reconsidered on that new evidence.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from amoeba.store import (
    BlockedKind,
    CommandKind,
    NodeKind,
    Store,
    StoreSchemaError,
)
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    read_schema_version,
)

PROJECT = "demo"

SQ_PARAMETERS: dict[str, object] = {"pipeline": "p6", "params": {"slice": "102"}}


def _populate(store: Store) -> tuple[str, str]:
    """Write a node, a blocked state, and a journal entry. Returns their ids."""
    node = store.create_node(
        project_id=PROJECT, kind=NodeKind.SLICE, title="observable"
    )
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )
    blocked = store.create_node(project_id=PROJECT, kind=NodeKind.GATE, title="waiting")
    store.block(blocked.id, kind=BlockedKind.HUMAN, context="needs a decision")
    return node.id, entry.id


def _read_only_uri(path: Path) -> str:
    """The SQLite URI the read-only handle opens with."""
    return f"file:{path}?mode=ro"


# --------------------------------------------------------------------------
# Task 2.1: the measurement itself, against raw sqlite3
# --------------------------------------------------------------------------


def test_mode_ro_reads_a_wal_store_with_no_writer_alive(store_file: Path) -> None:
    """The risk, measured: mode=ro against a WAL store whose writer is closed.

    This is the inspection case when the resident process is stopped.
    """
    with Store.open(store_file) as store:
        node_id, _ = _populate(store)
        assert (
            store._connection.execute(  # pyright: ignore[reportPrivateUsage]
                "PRAGMA journal_mode"
            ).fetchone()[0]
            == "wal"
        )

    connection = sqlite3.connect(_read_only_uri(store_file), uri=True)
    try:
        rows = connection.execute("SELECT id, title FROM nodes").fetchall()
    finally:
        connection.close()

    assert node_id in {str(row[0]) for row in rows}


def test_mode_ro_reads_a_wal_store_while_a_writer_is_alive(
    store_file: Path, tmp_path: Path
) -> None:
    """The real inspection case: a live writer in a separate process.

    The writer is a genuine subprocess holding an open store with uncommitted-
    then-committed data, not a second connection in this process, because the
    ``-shm`` behavior this measures is cross-process.
    """
    writer_script = tmp_path / "writer.py"
    writer_script.write_text(
        textwrap.dedent(
            f"""
            import sys, time
            from pathlib import Path
            from amoeba.store import Store, NodeKind

            with Store.open(Path({str(store_file)!r})) as store:
                store.create_node(
                    project_id={PROJECT!r}, kind=NodeKind.SLICE, title="from-writer"
                )
                print("ready", flush=True)
                # Hold the store open until the reader has finished.
                sys.stdin.readline()
            """
        ),
        encoding="utf-8",
    )

    writer = subprocess.Popen(
        [sys.executable, str(writer_script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert writer.stdout is not None
        assert writer.stdout.readline().strip() == "ready"

        connection = sqlite3.connect(_read_only_uri(store_file), uri=True)
        try:
            titles = {
                str(row[0])
                for row in connection.execute("SELECT title FROM nodes").fetchall()
            }
        finally:
            connection.close()
    finally:
        assert writer.stdin is not None
        writer.stdin.write("\n")
        writer.stdin.flush()
        writer.wait(timeout=10)

    assert "from-writer" in titles


def test_mode_ro_refuses_a_write(store_file: Path) -> None:
    """The evidence that made the fallback unnecessary: writes actually fail."""
    with Store.open(store_file) as store:
        _populate(store)

    connection = sqlite3.connect(_read_only_uri(store_file), uri=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("UPDATE nodes SET title = 'mutated'")
            connection.commit()
    finally:
        connection.close()


# --------------------------------------------------------------------------
# Task 2.3: the guarantees Store.open_read_only makes
# --------------------------------------------------------------------------


def test_read_only_open_reads_nodes_blocked_states_and_journal(
    store_file: Path,
) -> None:
    """A read-only handle sees the same values a read-write open does."""
    with Store.open(store_file) as writer:
        node_id, entry_id = _populate(writer)
        expected_nodes = writer.nodes_for_project(PROJECT)
        expected_blocked = writer.blocked(PROJECT)
        expected_entries = writer.journal_entries(PROJECT)

    with Store.open_read_only(store_file) as reader:
        assert reader.nodes_for_project(PROJECT) == expected_nodes
        assert reader.blocked(PROJECT) == expected_blocked
        assert reader.journal_entries(PROJECT) == expected_entries
        assert reader.get_node(node_id) is not None
        assert reader.journal_entry(entry_id) is not None
        assert [entry.id for entry in reader.unresolved_journal_entries(PROJECT)] == [
            entry_id
        ]


def test_every_write_through_a_read_only_handle_raises(store_file: Path) -> None:
    """Inspection cannot mutate a store, even by calling a write method.

    Task 2.1's evidence supported true ``mode=ro``, so this assertion applies
    rather than being deferred to the guard test.
    """
    with Store.open(store_file) as writer:
        node_id, entry_id = _populate(writer)

    with Store.open_read_only(store_file) as reader:
        with pytest.raises(sqlite3.OperationalError):
            reader.create_node(
                project_id=PROJECT, kind=NodeKind.SLICE, title="should not exist"
            )
        with pytest.raises(sqlite3.OperationalError):
            reader.block(node_id, kind=BlockedKind.HUMAN, context="no")
        with pytest.raises(sqlite3.OperationalError):
            reader.journal_issue(
                node_id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
            )
        with pytest.raises(sqlite3.OperationalError):
            reader.journal_escalate(entry_id, reason="no")

    # Nothing landed.
    with Store.open(store_file) as verifier:
        assert len(verifier.nodes_for_project(PROJECT)) == 2
        entry = verifier.journal_entry(entry_id)
        assert entry is not None
        assert entry.is_resolved is False


def test_read_only_open_never_migrates(store_file: Path) -> None:
    """A store below the expected version raises and is left untouched.

    The file's stamped version is checked directly afterward, not merely the
    call's failure: a handle that raised *after* migrating would still have
    mutated the store.
    """
    connection = sqlite3.connect(store_file)
    try:
        migrate(connection, expected_version=EXPECTED_SCHEMA_VERSION - 1)
    finally:
        connection.close()

    with pytest.raises(StoreSchemaError):
        Store.open_read_only(store_file)

    verifier = sqlite3.connect(store_file)
    try:
        assert read_schema_version(verifier) == EXPECTED_SCHEMA_VERSION - 1
    finally:
        verifier.close()


def test_read_only_open_refuses_a_store_newer_than_the_code(
    store_file: Path,
) -> None:
    """The newer-than-code rule holds for read-only opens too."""
    from amoeba.store import sql

    with Store.open(store_file) as store:
        _populate(store)

    connection = sqlite3.connect(store_file)
    try:
        connection.execute(
            sql.UPSERT_SCHEMA_VERSION,
            (sql.SCHEMA_META_ROW_ID, EXPECTED_SCHEMA_VERSION + 1),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(StoreSchemaError):
        Store.open_read_only(store_file)


def test_read_only_open_does_not_create_a_store(tmp_path: Path) -> None:
    """Inspecting a path with no store leaves the filesystem alone."""
    missing = tmp_path / "nothing-here.sqlite3"

    with pytest.raises(Exception):  # noqa: B017 - the type is asserted below
        Store.open_read_only(missing)

    assert not missing.exists()
    assert list(tmp_path.iterdir()) == []


def test_read_only_open_of_a_missing_store_raises_a_store_error(
    tmp_path: Path,
) -> None:
    """The failure is typed, so a caller never mistakes it for an empty store."""
    from amoeba.store import StoreError

    with pytest.raises(StoreError):
        Store.open_read_only(tmp_path / "absent.sqlite3")
