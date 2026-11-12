"""Moving state out of ``~/.config/amoeba`` on first use (slice 228, D2).

``prepare_state_home`` moves the legacy store and directories to the state home
(steps in ``state_move_store`` and ``state_move_dirs``); ``open_state_store`` is the
only function that opens the store, so no entry point can create an empty state-home
store before the move. ``config.yaml`` is never touched.
"""

from __future__ import annotations

import fcntl
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from amoeba.config.home import STORE_FILE_NAME, StateLayout
from amoeba.operations.state_move_dirs import has_legacy_state, move_directories
from amoeba.operations.state_move_store import move_store
from amoeba.operations.state_move_types import MoveHooks, MoveReport, MoveStep
from amoeba.store.errors import StoreBusyError, StoreRelocateError
from amoeba.store.store import BUSY_TIMEOUT_SECONDS, Store

__all__ = [
    "MoveHooks",
    "MoveReport",
    "MoveStep",
    "open_state_store",
    "prepare_state_home",
]


#: Held by the process doing the move, so two processes never both move directories
#: (the legacy store's own lock ends when that store is deleted). One empty file in
#: the state home, created only when there is legacy state to move; deleting it is
#: harmless.
MOVE_LOCK_NAME: Final = ".state-move.lock"
LOCK_POLL_SECONDS: Final = 0.01


@contextmanager
def _move_lock(state_home: Path, timeout_seconds: float) -> Generator[None]:
    """Hold an exclusive lock on the state home's move lock file.

    Raises:
        StoreBusyError: Another process held it for the whole timeout.
    """
    deadline = time.monotonic() + timeout_seconds
    with (state_home / MOVE_LOCK_NAME).open("a") as handle:
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                # Another process is moving; wait for it, up to the timeout.
                if time.monotonic() > deadline:
                    raise StoreBusyError(
                        f"another amoeba process held the state move for "
                        f"{timeout_seconds}s"
                    ) from None
                time.sleep(LOCK_POLL_SECONDS)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def prepare_state_home(
    layout: StateLayout,
    *,
    hooks: MoveHooks = MoveHooks(),  # noqa: B008  frozen: nothing to share or mutate
    busy_timeout_seconds: float = BUSY_TIMEOUT_SECONDS,
) -> MoveReport:
    """Move legacy state to the state home; does nothing when there is none.

    Writes one stderr line when something moved. ``hooks`` and
    ``busy_timeout_seconds`` are the crash-test, cross-filesystem and lock seams;
    production passes neither.

    Raises:
        StoreBusyError: The legacy store stayed locked past the timeout.
        StoreRelocateError: A copy failed, did not verify, or a directory could not
            be moved; any ``OSError`` of the move arrives as this.
    """
    legacy = layout.legacy_home
    if legacy is None or not has_legacy_state(legacy, STORE_FILE_NAME):
        return MoveReport(store_moved=False, entries_moved=0)
    try:
        layout.state_home.mkdir(parents=True, exist_ok=True)
        with _move_lock(layout.state_home, busy_timeout_seconds):
            # A process that held the lock before this one may have finished it.
            if not has_legacy_state(legacy, STORE_FILE_NAME):
                return MoveReport(store_moved=False, entries_moved=0)
            store_moved = False
            if (legacy / STORE_FILE_NAME).exists():
                store_moved = move_store(layout, hooks, busy_timeout_seconds)
            report = MoveReport(
                store_moved=store_moved, entries_moved=move_directories(layout, hooks)
            )
    except OSError as error:
        # Any filesystem failure of the move (lock file, rename, copy) is one
        # relocate error, so the CLI boundary reports it and exits 3.
        raise StoreRelocateError(
            f"cannot move state from {legacy} to {layout.state_home}: {error}"
        ) from error
    if report.moved_anything:
        sys.stderr.write(
            f"amoeba: moved state from {legacy} to {layout.state_home} "
            f"(store: {'moved' if report.store_moved else 'not moved'}, "
            f"{report.entries_moved} directory entries)\n"
        )
    return report


def open_state_store(layout: StateLayout) -> Store:
    """Move legacy state, then open (and migrate) the store at the state home."""
    prepare_state_home(layout)
    return Store.open(layout.store_path)
