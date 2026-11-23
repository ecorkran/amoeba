"""Moving state out of ``~/.config/amoeba`` on first use (slice 228, D2).

``prepare_state_home`` moves the legacy store and directories to the state home
(steps in ``state_move_store`` and ``state_move_dirs``); ``open_state_store`` is the
only function that opens the store, so no entry point can create an empty state-home
store before the move. ``config.yaml`` is never touched.
"""

from __future__ import annotations

import fcntl
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from amoeba.client.client_file import read_client_address
from amoeba.config.home import STORE_FILE_NAME, StateLayout
from amoeba.operations.naming import name_members
from amoeba.operations.state_move_dirs import has_legacy_state, move_directories
from amoeba.operations.state_move_store import move_store
from amoeba.operations.state_move_types import MoveHooks, MoveReport, MoveStep
from amoeba.store.errors import (
    HubHomeError,
    LocalStoreClosedError,
    StoreBusyError,
    StoreRelocateError,
)
from amoeba.store.machines import act_as_local
from amoeba.store.set_aside import set_aside_stores
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


def refuse_joined_or_hub_home(layout: StateLayout) -> None:
    """Refuse before any store or directory is touched (260 D2).

    A client file means this machine is joined: its store lives at the hub. A
    ``hub.yaml`` means this home is a hub's: its store is served, never written
    behind the door.

    Raises:
        LocalStoreClosedError: A client file exists; names the hub's address.
        HubHomeError: The config home holds ``hub.yaml``.
    """
    refuse_local_store_if_joined(layout)
    if layout.hub_file.exists():
        raise HubHomeError(
            f"this home is a hub's ({layout.hub_file} exists): its store is served "
            "by `amoeba hub serve`, so no other command opens it. Run ordinary "
            "commands from a machine joined to the hub"
        )


def refuse_local_store_if_joined(layout: StateLayout) -> None:
    """Raise ``LocalStoreClosedError`` naming the hub when a client file exists."""
    if layout.client_file.exists():
        address = read_client_address(layout.client_file)
        raise LocalStoreClosedError(
            f"this machine is joined to the hub at {address}, so there is no local "
            "store. Run `amoeba leave` to go back to a local store"
        )


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
    refuse_joined_or_hub_home(layout)
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


def _refuse_set_aside_without_store(layout: StateLayout) -> None:
    """A set-aside store and no store: the machine is joined or mid-join (D4).

    Creating a store here would give the machine a second one beside the set-aside
    store, so the opener refuses and names the command that ends it.
    """
    if layout.store_path.exists():
        return
    aside = set_aside_stores(layout.store_path)
    if aside:
        raise LocalStoreClosedError(
            f"the local store was set aside at {aside[-1]} for a hub, and there is "
            "no store at "
            f"{layout.store_path}. Run `amoeba leave` to put it back"
        )


def open_state_store(layout: StateLayout) -> Store:
    """Move legacy state, then open (and migrate) the store at the state home.

    The store acts as the machine ``local``, made on the first open (D12), so every
    record it inserts carries the install's one owner and machine.

    Raises:
        LocalStoreClosedError: This machine is joined, or its store was set aside.
        HubHomeError: This home is a hub's.
    """
    refuse_joined_or_hub_home(layout)
    _refuse_set_aside_without_store(layout)
    prepare_state_home(layout)
    store = Store.open(layout.store_path)
    ready = False
    try:
        act_as_local(store)
        # Name the members from before migration 012 before anything reads one (261 D4).
        name_members(store, subprocess.run, subprocess.run)
        ready = True
    finally:
        # A store that cannot act as `local` or be named is closed, not handed out;
        # the failure propagates.
        if not ready:
            store.close()
    return store
