"""``amoeba hub serve --from-backup``: put a backup's store, certificate and key in the
state directory (slice 260, D14, "Restoring from a backup").

A restore that is stopped anywhere is finished by running the same command again. The
six steps are in order; ``RestoreHooks`` is the fault seam. The files a restore moves
away are kept in ``replaced-<stamp>/`` directories, and only the newest ``kept`` of
them stay (the same count as each kind of backup), so they never pile up.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from amoeba.config.home import HUB_CERT_FILE_NAME, HUB_KEY_FILE_NAME, STORE_FILE_NAME
from amoeba.hub.backups import DIRECTORY_MODE, STAMP_FORMAT
from amoeba.hub.errors import HubStartError

#: Present from step 3 to step 6: its presence is what makes a start say a restore
#: did not finish.
PARTIAL_DIR_NAME: Final = "restore.partial"
#: ``replaced-<UTC stamp>``: where the files a restore moved away go. Never read;
#: the oldest beyond ``backups_kept`` are deleted when a restore finishes.
REPLACED_PREFIX: Final = "replaced-"
#: SQLite's side files of the store.
SIDE_FILE_SUFFIXES: Final = ("-wal", "-shm")
QUICK_CHECK_OK: Final = "ok"
#: The three files of a backup, in the order they are placed (the store last).
PLACE_ORDER: Final = (HUB_CERT_FILE_NAME, HUB_KEY_FILE_NAME, STORE_FILE_NAME)

type Step = Callable[[], None] | None


@dataclass(frozen=True)
class RestoreHooks:
    """One optional callable after each step of the restore. Production passes none."""

    after_partial_made: Step = None
    after_files_moved: Step = None
    after_files_copied: Step = None
    after_certificate_placed: Step = None
    after_key_placed: Step = None
    after_store_placed: Step = None


def _call(step: Step) -> None:
    if step is not None:
        step()


def _check_backup(backup: Path) -> None:
    """Step 1: the three files are there and the store opens and passes quick_check."""
    if not backup.is_dir():
        raise HubStartError(f"the backup {backup} is not a directory")
    absent = [name for name in PLACE_ORDER if not (backup / name).is_file()]
    if absent:
        raise HubStartError(f"the backup {backup} is missing {', '.join(absent)}")
    store = backup / STORE_FILE_NAME
    try:
        with closing(sqlite3.connect(f"{store.as_uri()}?mode=ro", uri=True)) as copy:
            verdict = [row[0] for row in copy.execute("PRAGMA quick_check")]
    except sqlite3.Error as error:
        raise HubStartError(
            f"the store in the backup {backup} is not a readable database: {error}"
        ) from error
    if verdict != [QUICK_CHECK_OK]:
        raise HubStartError(
            f"the store in the backup {backup} failed its quick_check: {verdict[:3]}"
        )


def _state_holds_a_working_hub(state_dir: Path) -> bool:
    return all((state_dir / name).exists() for name in PLACE_ORDER)


def _move_aside(state_dir: Path, now: datetime) -> Path | None:
    """Step 4: the store, its side files, the certificate and the key, whichever
    exist, into one new ``replaced-<UTC stamp>/``. No directory when none exist."""
    names = [
        *PLACE_ORDER,
        *(f"{STORE_FILE_NAME}{suffix}" for suffix in SIDE_FILE_SUFFIXES),
    ]
    present = [name for name in names if (state_dir / name).exists()]
    if not present:
        return None
    stamp = now.astimezone(UTC).strftime(STAMP_FORMAT)
    replaced = state_dir / f"{REPLACED_PREFIX}{stamp}"
    attempt = 1
    while replaced.exists():
        # Never merge into an earlier restore's directory: take the next free name.
        attempt += 1
        replaced = state_dir / f"{REPLACED_PREFIX}{stamp}-{attempt}"
    replaced.mkdir(mode=DIRECTORY_MODE)
    for name in present:
        (state_dir / name).rename(replaced / name)
    return replaced


def _prune_replaced(state_dir: Path, kept: int) -> None:
    """Delete the ``replaced-`` directories beyond the newest ``kept``.

    The names sort by time (a stamp, then ``-N`` for a repeat in one microsecond).
    A directory that cannot be deleted now is left for the next restore's pass: the
    restore itself is finished, and running it again would be refused.
    """
    found = sorted(
        path for path in state_dir.glob(f"{REPLACED_PREFIX}*") if path.is_dir()
    )
    for stale in found[: max(len(found) - kept, 0)]:
        shutil.rmtree(stale, ignore_errors=True)


def restore_from_backup(  # noqa: PLR0913 - the backup, its target, the clock and the seam
    backup: Path,
    state_dir: Path,
    now: datetime,
    kept: int,
    hooks: RestoreHooks = RestoreHooks(),  # noqa: B008  frozen, no state to share
) -> Path | None:
    """Restore ``backup`` into ``state_dir``; returns the ``replaced-`` directory the
    old files went to, or ``None`` when there were none to move. ``kept`` is how many
    ``replaced-`` directories stay (``backups_kept``); older ones are deleted once the
    restore is complete.

    Raises:
        HubStartError: The backup is not usable (state untouched), or the state
            directory holds a working hub (nothing changed), or a file operation
            failed (running the same command again finishes the restore).
    """
    _check_backup(backup)
    partial = state_dir / PARTIAL_DIR_NAME
    if _state_holds_a_working_hub(state_dir) and not partial.exists():
        raise HubStartError(
            f"{state_dir} already holds a working hub ({', '.join(PLACE_ORDER)}); "
            "a restore replaces nothing that works"
        )
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(partial, ignore_errors=True)
        partial.mkdir(mode=DIRECTORY_MODE)
        _call(hooks.after_partial_made)
        replaced = _move_aside(state_dir, now)
        _call(hooks.after_files_moved)
        for name in PLACE_ORDER:
            shutil.copy2(backup / name, partial / name)
        _call(hooks.after_files_copied)
        placed = (
            (HUB_CERT_FILE_NAME, hooks.after_certificate_placed),
            (HUB_KEY_FILE_NAME, hooks.after_key_placed),
            (STORE_FILE_NAME, hooks.after_store_placed),
        )
        for name, after in placed:
            (partial / name).rename(state_dir / name)
            _call(after)
        shutil.rmtree(partial)
    except OSError as error:
        raise HubStartError(
            f"the restore from {backup} stopped: {error}; run the same command again"
        ) from error
    _prune_replaced(state_dir, kept)
    return replaced
