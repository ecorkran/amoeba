"""What ``prune`` returns and how callers hold it (slice 228, D9).

A leaf module: ``Deps`` carries a ``Prune`` and so cannot import ``prune`` itself, which
reads the answering and resume logs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from amoeba.store.store import Store


@dataclass(frozen=True)
class PruneReport:
    """What a prune pass did: how many entries it removed, and what it could not."""

    removed: int
    #: One text per entry that could not be read or removed.
    problems: tuple[str, ...]

    def note(self) -> str | None:
        """The problems as one line for a calls-log ``detail``; ``None`` if none."""
        return "; ".join(self.problems) if self.problems else None


class Prune(Protocol):
    """``prune`` with the layout bound: removes what is settled and old."""

    def __call__(
        self, store: Store, /, *, now: datetime, after_days: int
    ) -> PruneReport:
        """Remove entries older than ``after_days`` that no open question needs."""
        ...
