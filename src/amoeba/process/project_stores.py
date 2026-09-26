"""The open set of project stores — the one module that writes.

Every read-write ``Store.open`` in the package happens here, which
``tests/test_writer_guard.py`` enforces mechanically by walking the AST of
every module under ``src/amoeba/``. The sole-writer model is completed by the
instance lock: at most one resident process per supervisor directory, and
within that process exactly one module that opens a store for writing.

Extracted from ``host.py``, which now delegates. The split keeps the loop
module near its line budget and gives the read-write open a single home that
does not also carry process lifetime, signals, and the grace watchdog.
"""

from __future__ import annotations

import logging
from pathlib import Path

from amoeba.process.errors import StartupFailedError
from amoeba.process.supervisor import discover_project_ids, store_path_for
from amoeba.store import Store, StoreError
from amoeba.store.paths import STORE_CREATING_SUFFIX, validate_project_id

logger = logging.getLogger(__name__)

#: The files SQLite keeps beside a WAL-mode database while it is open.
_SQLITE_SIDECAR_SUFFIXES = ("-wal", "-shm")


def _create_atomically(path: Path) -> None:
    """Build and migrate a new store beside ``path``, then rename it into place.

    A reader polling for the store — the documented way a submitter learns its
    project exists — then finds it either absent or complete, never at an
    earlier schema version mid-migration. A crash part-way leaves only the
    temporary file, which discovery ignores and the next attempt replaces.

    Raises:
        StoreError: If the store cannot be built, or SQLite left its write-ahead
            log behind on close (renaming would strand committed pages in it).
    """
    building = path.with_name(path.name + STORE_CREATING_SUFFIX)
    for leftover in (building, *_sidecars(building)):
        leftover.unlink(missing_ok=True)

    Store.open(building).close()
    if any(sidecar.exists() for sidecar in _sidecars(building)):
        raise StoreError(f"SQLite left its write-ahead log behind for {building}")
    building.replace(path)


def _sidecars(path: Path) -> tuple[Path, ...]:
    return tuple(
        path.with_name(path.name + suffix) for suffix in _SQLITE_SIDECAR_SUFFIXES
    )


class ProjectStores:
    """Every project store the resident process holds open, read-write."""

    def __init__(self, store_dir: Path) -> None:
        """Build an empty open set. Nothing is opened until :meth:`open_all`.

        Args:
            store_dir: The supervisor directory holding the project stores.
        """
        self._store_dir = store_dir
        self._stores: dict[str, Store] = {}

    def open_all(self) -> None:
        """Open every project's store read-write.

        Raises:
            StartupFailedError: If any store cannot be opened. A corrupt store
                for one project stops the whole supervisor, deliberately.
        """
        for project_id in discover_project_ids(self._store_dir):
            path = store_path_for(self._store_dir, project_id)
            try:
                self._stores[project_id] = Store.open(path)
            except Exception as error:
                logger.exception("cannot open the store for project %s", project_id)
                raise StartupFailedError(
                    f"cannot open the store for project {project_id!r}: {error}"
                ) from error

    def open_project(self, project_id: str) -> Store:
        """Create-or-open a project's store read-write and add it to the set.

        Idempotent: an already-open project returns its open handle. A new
        store is built under a temporary name and renamed into place only once
        fully migrated, so an outside reader never sees it half-built. Its
        journal is empty, so there is nothing to recover. :attr:`project_ids`
        includes it at once.

        Raises:
            ValueError: If ``project_id`` is not a safe filename. Checked
                before any path is computed, so nothing is created.
            StoreError: If the store cannot be created or opened. Not caught
                here — the caller decides what a failure means.
        """
        if (open_store := self._stores.get(project_id)) is not None:
            return open_store

        validate_project_id(project_id)
        path = store_path_for(self._store_dir, project_id)
        if not path.exists():
            _create_atomically(path)
        store = Store.open(path)
        self._stores[project_id] = store
        logger.info("opened project %s at runtime", project_id)
        return store

    def store_for(self, project_id: str) -> Store:
        """The open read-write store for a project.

        Raises:
            KeyError: If the project has no store open: it existed neither at
                start nor was opened since through :meth:`open_project`.
        """
        return self._stores[project_id]

    @property
    def project_ids(self) -> tuple[str, ...]:
        """The projects held open."""
        return tuple(self._stores)

    def items(self) -> tuple[tuple[str, Store], ...]:
        """Every open project and its store, as a stable snapshot.

        A snapshot rather than a live view because recovery iterates it while
        the set may gain a project, once runtime creation exists.
        """
        return tuple(self._stores.items())

    def close_all(self) -> None:
        """Close every open store. Runs on every exit path."""
        for project_id, store in self._stores.items():
            try:
                store.close()
            except Exception:
                # Logged and swallowed deliberately: this runs in the teardown
                # path, and a failure to close one store must not prevent
                # closing the rest or releasing the lock. Crash-only makes an
                # unclosed store recoverable anyway.
                logger.exception("error closing the store for project %s", project_id)
        self._stores.clear()
