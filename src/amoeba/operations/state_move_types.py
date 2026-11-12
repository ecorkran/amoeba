"""The vocabulary of the legacy-state move (slice 228, D2): steps, hooks, report."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class MoveStep(StrEnum):
    """The points of the move at which a test may stop it to simulate a crash."""

    OPENED = "opened"
    LOCKED = "locked"
    BACKED_UP = "backed_up"
    VERIFIED = "verified"
    PLACED = "placed"
    LEGACY_DELETED = "legacy_deleted"
    DIRECTORY_MOVED = "directory_moved"


def _no_step(step: MoveStep) -> None:
    """Production's ``after_step``: nothing happens between steps."""


def _move_directory(source: Path, destination: Path) -> None:
    """Production's mover: ``shutil.move``, which copies across filesystems."""
    shutil.move(source, destination)


@dataclass(frozen=True)
class MoveHooks:
    """The test seams of the move. Production passes the defaults."""

    #: Called after each step completes; raising simulates a crash right there.
    after_step: Callable[[MoveStep], None] = field(default=_no_step)
    #: Moves one entry; a test injects a copy-then-delete mover.
    move_directory: Callable[[Path, Path], None] = field(default=_move_directory)


@dataclass(frozen=True)
class MoveReport:
    """What one call moved."""

    store_moved: bool
    entries_moved: int

    @property
    def moved_anything(self) -> bool:
        return self.store_moved or self.entries_moved > 0
