"""``follow``: cursor, waking, resume, and every row of the failure table."""

from __future__ import annotations

import queue
import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.feed import FeedSettings, follow
from amoeba.store import (
    Change,
    NodeKind,
    Store,
    StoreBusyError,
    StorePermissionError,
    StoreSchemaError,
)
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION, migrate
from amoeba.store.paths import project_store_path

PROJECT = "demo"
FAST = FeedSettings(follow_interval_seconds=0.005, feed_batch_size=500)
#: Generous: a change must arrive well inside this, never near it.
WAKE_DEADLINE_SECONDS = 5.0


@pytest.fixture
def writer(supervisor_dir: Path) -> Iterator[Store]:
    with Store.open(project_store_path(supervisor_dir, PROJECT)) as store:
        yield store


def _add_nodes(store: Store, count: int) -> list[str]:
    return [
        store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n").id
        for _ in range(count)
    ]


def _take(iterator: Iterator[Change], count: int) -> list[Change]:
    return [next(iterator) for _ in range(count)]


class _StopAfter:
    """A ``stop`` that turns true once the follower has seen ``count`` changes."""

    def __init__(self, seen: list[Change], count: int) -> None:
        self._seen = seen
        self._count = count

    def __call__(self) -> bool:
        return len(self._seen) >= self._count


def _collect(
    supervisor_dir: Path, after: int, count: int, settings: FeedSettings = FAST
):
    seen: list[Change] = []
    for change in follow(
        supervisor_dir,
        PROJECT,
        after=after,
        settings=settings,
        stop=_StopAfter(seen, count),
    ):
        seen.append(change)
    return seen


# --------------------------------------------------------------------------
# Cursor and batching
# --------------------------------------------------------------------------


def test_after_zero_yields_every_change(supervisor_dir: Path, writer: Store) -> None:
    ids = _add_nodes(writer, 3)
    assert [c.node_id for c in _collect(supervisor_dir, 0, 3)] == ids


def test_after_n_yields_exactly_the_later_changes(
    supervisor_dir: Path, writer: Store
) -> None:
    _add_nodes(writer, 4)
    assert [c.seq for c in _collect(supervisor_dir, 2, 2)] == [3, 4]


def test_small_batches_deliver_everything_in_order(
    supervisor_dir: Path, writer: Store
) -> None:
    _add_nodes(writer, 5)
    settings = FeedSettings(follow_interval_seconds=0.005, feed_batch_size=2)
    assert [c.seq for c in _collect(supervisor_dir, 0, 5, settings)] == [1, 2, 3, 4, 5]


# --------------------------------------------------------------------------
# Waking and resume
# --------------------------------------------------------------------------


def test_a_new_commit_wakes_an_idle_follower(
    supervisor_dir: Path, writer: Store
) -> None:
    arrived: queue.Queue[Change] = queue.Queue()
    done = threading.Event()

    def consume() -> None:
        for change in follow(
            supervisor_dir, PROJECT, after=0, settings=FAST, stop=done.is_set
        ):
            arrived.put(change)

    thread = threading.Thread(target=consume)
    thread.start()
    try:
        (node_id,) = _add_nodes(writer, 1)
        assert arrived.get(timeout=WAKE_DEADLINE_SECONDS).node_id == node_id
    finally:
        done.set()
        thread.join(timeout=WAKE_DEADLINE_SECONDS)
    assert not thread.is_alive()


def test_resume_from_the_last_seq_has_no_gap_and_no_repeat(
    supervisor_dir: Path, writer: Store
) -> None:
    _add_nodes(writer, 5)
    first = _take(follow(supervisor_dir, PROJECT, after=0, settings=FAST), 2)
    rest = _collect(supervisor_dir, first[-1].seq, 3)
    assert [c.seq for c in first + rest] == [1, 2, 3, 4, 5]
    assert len(writer.changes(PROJECT, limit=100)) == 5


# --------------------------------------------------------------------------
# The failure table
# --------------------------------------------------------------------------


def test_an_unknown_project_raises_before_any_yield(supervisor_dir: Path) -> None:
    with pytest.raises(StorePermissionError):
        next(follow(supervisor_dir, "nobody", after=0, settings=FAST))


def test_a_store_at_another_schema_version_raises_before_any_yield(
    supervisor_dir: Path,
) -> None:
    path = project_store_path(supervisor_dir, PROJECT)
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        migrate(connection, expected_version=EXPECTED_SCHEMA_VERSION - 1)
    with pytest.raises(StoreSchemaError):
        next(follow(supervisor_dir, PROJECT, after=0, settings=FAST))


def test_a_missing_supervisor_directory_raises_before_any_yield(tmp_path: Path) -> None:
    with pytest.raises(StorePermissionError):
        next(follow(tmp_path / "gone", PROJECT, after=0, settings=FAST))


def test_a_store_removed_mid_follow_raises_on_a_later_read(
    supervisor_dir: Path, writer: Store
) -> None:
    _add_nodes(writer, 1)
    writer.close()
    iterator = follow(supervisor_dir, PROJECT, after=0, settings=FAST)
    next(iterator)
    for path in supervisor_dir.iterdir():
        path.unlink()
    with pytest.raises(StorePermissionError):
        next(iterator)


def test_a_busy_read_is_retried(
    supervisor_dir: Path, writer: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add_nodes(writer, 1)
    real_changes = Store.changes
    calls: list[int] = []

    def busy_once(self: Store, project_id: str, *, after: int = 0, limit: int):
        calls.append(after)
        if len(calls) == 1:
            raise StoreBusyError("held by a writer")
        return real_changes(self, project_id, after=after, limit=limit)

    monkeypatch.setattr(Store, "changes", busy_once)
    assert [c.seq for c in _collect(supervisor_dir, 0, 1)] == [1]
    assert len(calls) >= 2


def test_a_raising_stop_propagates(supervisor_dir: Path, writer: Store) -> None:
    _add_nodes(writer, 1)

    def broken() -> bool:
        raise RuntimeError("caller bug")

    with pytest.raises(RuntimeError, match="caller bug"):
        next(follow(supervisor_dir, PROJECT, after=0, settings=FAST, stop=broken))


def test_stop_true_ends_the_iterator_and_closes_the_store(
    supervisor_dir: Path, writer: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add_nodes(writer, 1)
    closed: list[bool] = []
    real_close = Store.close

    def recording_close(self: Store) -> None:
        closed.append(True)
        real_close(self)

    monkeypatch.setattr(Store, "close", recording_close)
    assert (
        list(follow(supervisor_dir, PROJECT, after=0, settings=FAST, stop=lambda: True))
        == []
    )
    assert closed == [True]
