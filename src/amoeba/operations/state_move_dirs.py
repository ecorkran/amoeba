"""Moving the legacy directories (slice 228, D2 step 5).

Each entry of the legacy ``answering/``, ``logs/answering/`` and ``logs/resume/`` goes
to the same place under the state home: first to ``.<name>.moving`` (``shutil.move``
copies across filesystems), then renamed. A leftover ``.<name>.moving`` is a crashed
move and is removed before the entry is moved again.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Final

from amoeba.config.home import ANSWERING_DIR_NAME, LOGS_DIR_NAME, StateLayout
from amoeba.operations.state_move_types import MoveHooks, MoveStep
from amoeba.store.errors import StoreRelocateError

logger = logging.getLogger(__name__)

#: Directories moved, relative to a home, and the order they are emptied in.
MOVED_DIRECTORIES: Final = (
    (ANSWERING_DIR_NAME,),
    (LOGS_DIR_NAME, "answering"),
    (LOGS_DIR_NAME, "resume"),
)
MOVING_PREFIX: Final = "."
MOVING_SUFFIX: Final = ".moving"


def has_legacy_state(legacy_home: Path, store_file_name: str) -> bool:
    """Whether the legacy home holds anything the move concerns."""
    return any(
        (legacy_home / name).exists()
        for name in (store_file_name, ANSWERING_DIR_NAME, LOGS_DIR_NAME)
    )


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _move_entry(entry: Path, destination_root: Path, hooks: MoveHooks) -> bool:
    """Move one entry; ``False`` when another process already took it."""
    temporary = destination_root / f"{MOVING_PREFIX}{entry.name}{MOVING_SUFFIX}"
    destination = destination_root / entry.name
    _remove(temporary)
    if not entry.exists():
        return False  # moved by a process that started the move before this one
    hooks.move_directory(entry, temporary)
    if destination.exists():
        # Run ids and log names are unique, so this is the same entry moved twice;
        # the one already in place wins and the copy just made is dropped.
        logger.warning(
            "%s already exists; dropping the legacy copy of %s", destination, entry
        )
        _remove(temporary)
    else:
        temporary.rename(destination)
    hooks.after_step(MoveStep.DIRECTORY_MOVED)
    return True


def _remove_if_empty(directory: Path) -> None:
    if directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()


def move_directories(layout: StateLayout, hooks: MoveHooks) -> int:
    """Move every legacy entry; returns how many this call moved.

    Raises:
        StoreRelocateError: An entry could not be moved.
    """
    legacy = layout.legacy_home
    assert legacy is not None
    moved = 0
    for parts in MOVED_DIRECTORIES:
        source_root = legacy.joinpath(*parts)
        if not source_root.is_dir():
            continue
        destination_root = layout.state_home.joinpath(*parts)
        try:
            destination_root.mkdir(parents=True, exist_ok=True)
            for entry in sorted(source_root.iterdir()):
                moved += _move_entry(entry, destination_root, hooks)
        except OSError as error:
            logger.exception("cannot move %s to %s", source_root, destination_root)
            raise StoreRelocateError(
                f"cannot move {source_root} to {destination_root}: {error}"
            ) from error
        _remove_if_empty(source_root)
    _remove_if_empty(legacy / LOGS_DIR_NAME)
    return moved
