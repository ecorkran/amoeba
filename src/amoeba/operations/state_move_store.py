"""Moving the legacy store file (slice 228, D2 steps 1 to 4 and "both stores exist").

The legacy store is locked with ``BEGIN IMMEDIATE`` (its own connection, never
``Store.open``, which would create a missing store). Under that lock the store is
copied and verified, or, when the state-home store already exists, compared with it.
The legacy files are deleted only after the lock is released. Every failure leaves
the legacy store as it was.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import sys
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from amoeba.config.home import STORE_FILE_NAME, StateLayout
from amoeba.operations.state_move_types import MoveHooks, MoveStep
from amoeba.store import sql
from amoeba.store.errors import StoreRelocateError, store_error_for
from amoeba.store.relocate import (
    SIDECAR_SUFFIXES,
    compare_stores,
    copy_store,
    summarize_store,
)

logger = logging.getLogger(__name__)

#: The copy in progress; renamed to the store file once verified.
MOVING_SUFFIX: Final = ".moving"
#: Where a differing legacy store is set aside, followed by a UTC stamp.
LEGACY_ASIDE_INFIX: Final = ".legacy-"
STAMP_FORMAT: Final = "%Y%m%dT%H%M%S%fZ"


def remove_store_files(store: Path) -> None:
    """Delete a store file and its ``-wal`` and ``-shm``; missing ones are fine."""
    for suffix in ("", *SIDECAR_SUFFIXES):
        Path(f"{store}{suffix}").unlink(missing_ok=True)


@contextmanager
def _legacy_lock(
    old: Path, busy_timeout_seconds: float, hooks: MoveHooks
) -> Generator[bool]:
    """Hold ``BEGIN IMMEDIATE`` on the legacy store; yields ``False`` when another
    process already finished the move (the file is gone).

    Raises:
        StoreBusyError: The lock was not granted within the timeout.
    """
    try:
        connection = sqlite3.connect(
            f"{old.as_uri()}?mode=rw",
            uri=True,
            timeout=busy_timeout_seconds,
            isolation_level=None,
        )
    except sqlite3.Error as error:
        if not old.exists():
            yield False  # the file went between the check and the open
            return
        logger.exception("cannot open the legacy store at %s", old)
        raise store_error_for(
            error, path=old, busy_timeout_seconds=busy_timeout_seconds
        ) from error
    try:
        hooks.after_step(MoveStep.OPENED)
        try:
            connection.execute(sql.BEGIN_IMMEDIATE)
        except sqlite3.Error as error:
            if not old.exists():
                yield False  # deleted under us: SQLite refuses a write on it
                return
            logger.exception("cannot lock the legacy store at %s", old)
            raise store_error_for(
                error, path=old, busy_timeout_seconds=busy_timeout_seconds
            ) from error
        if not old.exists():
            yield False  # a lock on a file already deleted succeeds; look again
            return
        hooks.after_step(MoveStep.LOCKED)
        yield True
    finally:
        connection.close()


def _place_copy(layout: StateLayout, old: Path, hooks: MoveHooks) -> None:
    """Copy, verify and rename into place (steps 2 to 4, before the legacy delete)."""
    legacy = layout.legacy_home
    assert legacy is not None
    moving = Path(f"{layout.store_path}{MOVING_SUFFIX}")
    # Only the lock holder reaches here, so a leftover is a crashed copy, never
    # another process's live one.
    remove_store_files(moving)
    copy_store(
        old,
        moving,
        str(legacy),
        str(layout.state_home),
        after_backup=lambda: hooks.after_step(MoveStep.BACKED_UP),
    )
    hooks.after_step(MoveStep.VERIFIED)
    moving.rename(layout.store_path)
    hooks.after_step(MoveStep.PLACED)


def _set_aside(layout: StateLayout, old: Path) -> None:
    """Move a differing legacy store into the state home and say so on stderr."""
    aside = layout.store_path.with_name(
        f"{STORE_FILE_NAME}{LEGACY_ASIDE_INFIX}{datetime.now(UTC).strftime(STAMP_FORMAT)}"
    )
    legacy_summary = summarize_store(old)
    for suffix in ("", *SIDECAR_SUFFIXES):
        source = Path(f"{old}{suffix}")
        if source.exists():
            shutil.move(source, Path(f"{aside}{suffix}"))
    sys.stderr.write(
        f"amoeba: the legacy store and {layout.store_path} both exist and differ; "
        f"kept {layout.store_path} ({summarize_store(layout.store_path)}) and set "
        f"the legacy store aside as {aside} ({legacy_summary})\n"
    )


def _same_stores(layout: StateLayout, old: Path) -> bool:
    legacy = layout.legacy_home
    assert legacy is not None
    try:
        compare_stores(old, layout.store_path, str(legacy), str(layout.state_home))
    except StoreRelocateError:
        return False  # logged by compare_stores; "differ" is the answer
    return True


def move_store(
    layout: StateLayout, hooks: MoveHooks, busy_timeout_seconds: float
) -> bool:
    """Run steps 1 to 4 for the legacy store file; ``True`` when this call placed it.

    Raises:
        StoreBusyError: The legacy store stayed locked past the timeout; nothing
            was written.
        StoreRelocateError: The copy failed or did not verify; the legacy store is
            untouched and the next call tries again.
    """
    legacy = layout.legacy_home
    assert legacy is not None
    old = legacy / STORE_FILE_NAME
    placed = False
    same = False
    differs = False
    with _legacy_lock(old, busy_timeout_seconds, hooks) as held:
        if held and not layout.store_path.exists():
            _place_copy(layout, old, hooks)
            placed = True
        elif held:
            same = _same_stores(layout, old)
            differs = not same
    if placed or same:
        remove_store_files(old)
        hooks.after_step(MoveStep.LEGACY_DELETED)
    elif differs:
        _set_aside(layout, old)
    else:
        # Another process finished the move; the connection we made may have left
        # sidecar files beside a store that is gone.
        remove_store_files(old)
    return placed
