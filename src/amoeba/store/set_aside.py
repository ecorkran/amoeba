"""Setting a store aside for a hub and putting it back (slice 260, D4).

A set-aside store is the local store, closed with the mark and renamed to
``<store file name>.set-aside-<UTC stamp>``. This module owns those names; the steps
that make and undo one follow the finder.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from amoeba.store import sql, sql_machines
from amoeba.store.errors import StoreRelocateError
from amoeba.store.relocate import SIDECAR_SUFFIXES, backup_store
from amoeba.store.row_values import encode_timestamp

#: Between the store's file name and the stamp: ``amoeba.sqlite3.set-aside-<stamp>``.
SET_ASIDE_MARKER: Final = ".set-aside-"
#: A copy in progress; renamed to a stamped name when complete.
PARTIAL_SUFFIX: Final = ".set-aside.partial"
#: ``%Y%m%dT%H%M%SZ``: sorts by time and has no character a file name dislikes.
STAMP_FORMAT: Final = "%Y%m%dT%H%M%SZ"


def set_aside_stores(store_path: Path) -> list[Path]:
    """The set-aside stores beside ``store_path``, oldest first.

    A side file of a set-aside store (``-wal``, ``-shm``) is not a store.
    """
    found = (
        path
        for path in store_path.parent.glob(f"{store_path.name}{SET_ASIDE_MARKER}*")
        if not path.name.endswith(SIDECAR_SUFFIXES)
    )
    return sorted(found)


DISPLACED_MARKER: Final = ".displaced-"
#: How many displaced stores stay. One is made only from a hand-placed file, so a few
#: are plenty; `leave` deletes the oldest beyond this when it makes another.
DISPLACED_STORES_KEPT: Final = 3


@dataclass(frozen=True)
class SetAsideHooks:
    """The fault seam of a set-aside: a stop simulated after each step, and one
    between the two deletes of step 4. Production passes none."""

    after_mark: Callable[[], None] | None = None
    after_copy: Callable[[], None] | None = None
    after_rename: Callable[[], None] | None = None
    #: After the store file is deleted and before its side files are.
    after_store_deleted: Callable[[], None] | None = None
    after_delete: Callable[[], None] | None = None


@dataclass(frozen=True)
class PutBack:
    """What `put_back` did."""

    #: The set-aside store renamed to the store path, if there was one.
    restored: Path | None
    #: Where a hand-placed store at the store path was moved, if one was.
    displaced: Path | None
    #: Whether a closed mark was cleared in place (no set-aside store existed).
    cleared_mark: bool


def _call(step: Callable[[], None] | None) -> None:
    if step is not None:
        step()


def _side_files(path: Path) -> list[Path]:
    return [Path(f"{path}{suffix}") for suffix in SIDECAR_SUFFIXES]


def _stamp(now: datetime) -> str:
    return now.astimezone(UTC).strftime(STAMP_FORMAT)


def _delete_store(path: Path) -> None:
    """The store file first, then its two side files."""
    path.unlink(missing_ok=True)
    for side in _side_files(path):
        side.unlink(missing_ok=True)


def clear_orphan_side_files(store_path: Path) -> None:
    """Delete ``-wal`` and ``-shm`` beside no store file: a restored store must never
    be read together with another store's write-ahead log (D4)."""
    if store_path.exists():
        return
    for side in _side_files(store_path):
        side.unlink(missing_ok=True)


def _mark_of(path: Path) -> tuple[str, str] | None:
    """The closed mark's ``(address, time)`` in the store at ``path``, read on a
    read-only plain connection. A store with no ``closed_mark`` table has none."""
    try:
        with closing(
            sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        ) as connection:
            row = connection.execute(sql_machines.SELECT_CLOSED_MARK).fetchone()
    except sqlite3.OperationalError as error:
        if "no such table" in str(error):
            return None
        raise
    return None if row is None else (str(row[0]), str(row[1]))


def holds_closed_mark(path: Path) -> bool:
    return _mark_of(path) is not None


def same_mark(path_a: Path, path_b: Path) -> bool:
    """True only when both stores hold a closed mark with the same address and time:
    the pair a stopped set-aside makes, the original and its copy."""
    mark_a, mark_b = _mark_of(path_a), _mark_of(path_b)
    return mark_a is not None and mark_a == mark_b


def _write_mark(store_path: Path, hub_address: str, now: datetime) -> None:
    """Step 1: the mark, on a plain connection (which makes no mark check), in one
    committed transaction, replacing any mark already there."""
    with closing(sqlite3.connect(store_path, isolation_level=None)) as connection:
        connection.execute(sql.BEGIN_IMMEDIATE)
        connection.execute(
            sql_machines.REPLACE_CLOSED_MARK, (hub_address, encode_timestamp(now))
        )
        connection.execute(sql.COMMIT)


def set_aside(
    store_path: Path,
    hub_address: str,
    now: datetime,
    hooks: SetAsideHooks = SetAsideHooks(),  # noqa: B008  frozen, no state to share
) -> Path:
    """Close the store at ``store_path`` with the mark, copy it aside and delete the
    original (D4's four steps); returns the set-aside path.

    The write-ahead log is never checkpointed and no side file is renamed, so nothing
    depends on other connections being closed. A set-aside store already present is
    the result of a stopped run when the store at the path is its original.

    Raises:
        StoreRelocateError: The mark or the copy failed, or a set-aside store and a
            store that is not its original both exist.
    """
    clear_orphan_side_files(store_path)
    existing = set_aside_stores(store_path)
    if existing:
        aside = existing[-1]
        if store_path.exists() and not same_mark(store_path, aside):
            raise StoreRelocateError(
                f"the set-aside store {aside} and the store {store_path} are not "
                "a pair `amoeba join` made; run `amoeba leave`, which puts the "
                "set-aside store back and moves the other to a dated name"
            )
        _delete_store(store_path)
        return aside
    try:
        _write_mark(store_path, hub_address, now)
    except sqlite3.Error as error:
        raise StoreRelocateError(f"cannot mark {store_path}: {error}") from error
    _call(hooks.after_mark)
    partial = Path(f"{store_path}{PARTIAL_SUFFIX}")
    _delete_store(partial)
    try:
        backup_store(store_path, partial)
    except (sqlite3.Error, OSError) as error:
        _delete_store(partial)
        raise StoreRelocateError(f"cannot copy {store_path}: {error}") from error
    _call(hooks.after_copy)
    aside = Path(f"{store_path}{SET_ASIDE_MARKER}{_stamp(now)}")
    partial.rename(aside)
    _call(hooks.after_rename)
    store_path.unlink(missing_ok=True)
    _call(hooks.after_store_deleted)
    for side in _side_files(store_path):
        side.unlink(missing_ok=True)
    _call(hooks.after_delete)
    return aside


def _clear_mark(path: Path) -> None:
    """Delete the closed mark in one transaction on a plain connection and close, so
    the store is one file again."""
    with closing(sqlite3.connect(path, isolation_level=None)) as connection:
        connection.execute(sql.BEGIN_IMMEDIATE)
        connection.execute(sql_machines.DELETE_CLOSED_MARK)
        connection.execute(sql.COMMIT)


def _displace(store_path: Path, now: datetime) -> Path:
    """Move a hand-placed store and its side files to a dated name; nothing of it is
    deleted."""
    displaced = Path(f"{store_path}{DISPLACED_MARKER}{_stamp(now)}")
    store_path.rename(displaced)
    for side, moved in zip(
        _side_files(store_path), _side_files(displaced), strict=True
    ):
        if side.exists():
            side.rename(moved)
    return displaced


def _prune_displaced(store_path: Path) -> None:
    """Delete the displaced stores beyond the newest ``DISPLACED_STORES_KEPT``, each
    with its side files. The stamps sort by time."""
    found = sorted(
        path
        for path in store_path.parent.glob(f"{store_path.name}{DISPLACED_MARKER}*")
        if not path.name.endswith(SIDECAR_SUFFIXES)
    )
    for stale in found[: max(len(found) - DISPLACED_STORES_KEPT, 0)]:
        _delete_store(stale)


def put_back(store_path: Path, now: datetime) -> PutBack:
    """Undo a set-aside, in D4's order; each part is skipped when already done.

    With no set-aside store and a store at the path holding the closed mark (a `join`
    stopped before its copy was renamed), the mark is cleared in place instead.

    Raises:
        StoreRelocateError: A side file is still beside the set-aside store after the
            mark was cleared (another process holds it open); running it again
            retries.
    """
    partial = Path(f"{store_path}{PARTIAL_SUFFIX}")
    _delete_store(partial)
    clear_orphan_side_files(store_path)
    existing = set_aside_stores(store_path)
    if not existing:
        cleared = store_path.exists() and holds_closed_mark(store_path)
        if cleared:
            _clear_mark(store_path)
        return PutBack(restored=None, displaced=None, cleared_mark=cleared)
    aside = existing[-1]
    displaced: Path | None = None
    if store_path.exists():
        if same_mark(store_path, aside):
            _delete_store(store_path)
        else:
            displaced = _displace(store_path, now)
            _prune_displaced(store_path)
    _clear_mark(aside)
    leftover = [side for side in _side_files(aside) if side.exists()]
    if leftover:
        raise StoreRelocateError(
            f"{leftover[0]} is still beside the set-aside store {aside}: another "
            "process has it open; close it and run `amoeba leave` again"
        )
    aside.rename(store_path)
    return PutBack(restored=aside, displaced=displaced, cleared_mark=False)
