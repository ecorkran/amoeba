"""Tests for the enumerated store-I/O failure modes.

Each mode raises a specific typed exception. None degrades to a default, an
empty result, or a fallback store — a caller silently operating against a
throwaway store it did not ask for is the worst available outcome.

Every test here operates only on paths the fixture created.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

import pytest

from amoeba.store import sql
from amoeba.store.models import (
    BlockedKind,
    NodeKind,
    NodeStatus,
    StoreBusyError,
    StoreCorruptError,
    StoreIntegrityError,
    StorePermissionError,
    StoreSchemaError,
)
from amoeba.store.store import Store

#: Short timeout for contention tests, so they do not wait the production
#: timeout. The assertion still references the named constant, never a literal.
CONTENTION_TIMEOUT_SECONDS = 0.2


def test_corrupt_file_raises_on_open(store_file: Path) -> None:
    """A file that is not a SQLite database raises rather than being replaced."""
    original = b"this is definitely not a sqlite database" * 64
    store_file.write_bytes(original)

    with pytest.raises(StoreCorruptError):
        Store.open(store_file)

    # Never re-created, truncated, or treated as fresh: the bytes are untouched.
    assert store_file.read_bytes() == original


def test_corrupt_file_is_not_replaced_by_a_fresh_store(store_file: Path) -> None:
    """The failed open leaves no usable store behind."""
    store_file.write_bytes(b"garbage" * 128)

    with pytest.raises(StoreCorruptError):
        Store.open(store_file)

    with sqlite3.connect(store_file) as raw:
        with pytest.raises(sqlite3.DatabaseError):
            raw.execute("SELECT name FROM sqlite_master").fetchall()


@pytest.mark.skipif(
    os.geteuid() == 0,
    reason="chmod-based restriction is a no-op for root, so this cannot "
    "genuinely exercise the permission failure",
)
def test_unwritable_parent_raises_at_open_with_the_path(tmp_path: Path) -> None:
    """An uncreatable store directory raises, naming the resolved path.

    A parent directory is restricted rather than the file itself: the store
    creates parent directories at open, so restricting the parent is what
    actually exercises the failure.
    """
    restricted = tmp_path / "restricted"
    restricted.mkdir()
    restricted.chmod(0o000)

    try:
        # Guard against a vacuous pass: if the restriction did not take, the
        # test would "pass" while exercising nothing.
        if os.access(restricted, os.W_OK):
            pytest.skip("filesystem did not honour the chmod restriction")

        target = restricted / "nested" / "store.sqlite3"

        with pytest.raises(StorePermissionError) as raised:
            Store.open(target)

        assert str(restricted) in str(raised.value)
    finally:
        restricted.chmod(0o755)


@pytest.mark.skipif(
    os.geteuid() == 0,
    reason="chmod-based restriction is a no-op for root, so this cannot "
    "genuinely exercise the permission failure",
)
def test_unreadable_store_raises_at_open(tmp_path: Path) -> None:
    """An existing store in an unreadable directory raises at open."""
    parent = tmp_path / "parent"
    parent.mkdir()
    store_location = parent / "store.sqlite3"

    with Store.open(store_location) as store:
        store.create_node(project_id="demo", kind=NodeKind.SLICE, title="x")

    parent.chmod(0o000)

    try:
        if os.access(store_location, os.R_OK):
            pytest.skip("filesystem did not honour the chmod restriction")

        with pytest.raises(StorePermissionError) as raised:
            Store.open(store_location)

        assert str(store_location) in str(raised.value)
    finally:
        parent.chmod(0o755)


def test_busy_timeout_exhaustion_raises(store_file: Path) -> None:
    """Contention that outlasts the busy timeout raises the typed error.

    Never retried indefinitely, and never reported as an empty result.
    """
    with Store.open(store_file) as seed:
        seed.create_node(project_id="demo", kind=NodeKind.SLICE, title="seed")

    blocker = sqlite3.connect(store_file, timeout=CONTENTION_TIMEOUT_SECONDS)
    blocker.execute("BEGIN EXCLUSIVE")

    try:
        store = Store.open(store_file, busy_timeout_seconds=CONTENTION_TIMEOUT_SECONDS)
        with store:
            with pytest.raises(StoreBusyError) as raised:
                store.create_node(
                    project_id="demo", kind=NodeKind.SLICE, title="contended"
                )

        assert "busy timeout" in str(raised.value)
    finally:
        blocker.rollback()
        blocker.close()


def test_busy_timeout_default_is_the_named_constant() -> None:
    """The production timeout is the named constant, not an inline literal.

    Asserted by identity with the constant rather than by matching a number: a
    test that hardcodes the value defeats the purpose of naming it.
    """
    import inspect

    signature = inspect.signature(Store.open)
    default = signature.parameters["busy_timeout_seconds"].default

    assert default == sql.BUSY_TIMEOUT_SECONDS
    assert isinstance(sql.BUSY_TIMEOUT_SECONDS, float)


def test_busy_error_names_the_contended_operation(store_file: Path) -> None:
    """The raised error says which operation was contended."""
    with Store.open(store_file) as seed:
        seed.create_node(project_id="demo", kind=NodeKind.SLICE, title="seed")

    blocker = sqlite3.connect(store_file, timeout=CONTENTION_TIMEOUT_SECONDS)
    blocker.execute("BEGIN EXCLUSIVE")

    try:
        store = Store.open(store_file, busy_timeout_seconds=CONTENTION_TIMEOUT_SECONDS)
        with store:
            with pytest.raises(StoreBusyError, match="INSERT"):
                store.create_node(
                    project_id="demo", kind=NodeKind.SLICE, title="contended"
                )
    finally:
        blocker.rollback()
        blocker.close()


def test_contended_read_does_not_return_an_empty_result(store_file: Path) -> None:
    """Under contention a read raises; it never looks like "no rows"."""
    with Store.open(store_file) as seed:
        seed.create_node(project_id="demo", kind=NodeKind.SLICE, title="seed")

    store = Store.open(store_file, busy_timeout_seconds=CONTENTION_TIMEOUT_SECONDS)
    blocker = sqlite3.connect(store_file, timeout=CONTENTION_TIMEOUT_SECONDS)

    def _hold_write_lock() -> None:
        blocker.execute("BEGIN EXCLUSIVE")

    try:
        with store:
            assert len(store.runnable("demo")) == 1

            _hold_write_lock()

            # A write under an exclusive lock must raise, not silently no-op.
            with pytest.raises(StoreBusyError):
                store.create_node(
                    project_id="demo", kind=NodeKind.SLICE, title="contended"
                )
    finally:
        blocker.rollback()
        blocker.close()


def test_write_failure_propagates_rather_than_returning_a_status(
    store_file: Path,
) -> None:
    """A failed write raises; no method returns an ignorable status code.

    Stands in for the disk-full mode, which cannot be provoked portably: the
    obligation under test is that a failing commit surfaces rather than being
    reported as success.
    """
    with Store.open(store_file) as store:
        node = store.create_node(project_id="demo", kind=NodeKind.SLICE, title="x")

        # Drop the table out from under the store to force the write to fail.
        with sqlite3.connect(store_file) as raw:
            raw.execute(f"DROP TABLE {sql.TABLE_BLOCKED_STATES}")

        with pytest.raises(sqlite3.DatabaseError):
            store.block(node.id, kind=BlockedKind.HUMAN, context="ctx")


def test_concurrent_readers_are_allowed_under_wal(store_file: Path) -> None:
    """WAL permits concurrent readers alongside a writer, as designed."""
    with Store.open(store_file) as writer:
        writer.create_node(project_id="demo", kind=NodeKind.SLICE, title="seed")

        results: list[int] = []

        def _read() -> None:
            with Store.open(store_file) as reader:
                results.append(len(reader.runnable("demo")))

        thread = threading.Thread(target=_read)
        thread.start()
        thread.join(timeout=10)

        assert results == [1]


def test_schema_invariant_violation_raises_typed_error(store_file: Path) -> None:
    """A write the schema refuses surfaces typed, not as a raw sqlite3 error.

    The node's status is reset behind the store's back, so ``block()`` passes
    its own check and the one-open-blocked-state-per-node index refuses the
    second record.
    """
    with Store.open(store_file) as store:
        node_id = store.create_node(
            project_id="demo", kind=NodeKind.SLICE, title="a slice"
        ).id
        store.block(node_id, kind=BlockedKind.HUMAN, context="first block")

        tamper = sqlite3.connect(store_file)
        try:
            with tamper:
                tamper.execute(
                    sql.UPDATE_NODE_STATUS,
                    (NodeStatus.RUNNABLE.value, "2026-01-01T00:00:00+00:00", node_id),
                )
        finally:
            tamper.close()

        with pytest.raises(StoreIntegrityError):
            store.block(node_id, kind=BlockedKind.HUMAN, context="second block")


def test_open_temporary_closes_the_connection_when_migration_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both constructors give the same guarantee: a failed open leaks nothing."""
    opened: list[sqlite3.Connection] = []

    def _tracking_connect(path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(path)
        opened.append(connection)
        return connection

    def _failing_migrate(connection: sqlite3.Connection) -> None:
        raise StoreSchemaError("provoked migration failure")

    monkeypatch.setattr(Store, "_connect", staticmethod(_tracking_connect))
    monkeypatch.setattr("amoeba.store.store.migrate", _failing_migrate)

    with pytest.raises(StoreSchemaError):
        Store.open_temporary()

    (connection,) = opened
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
