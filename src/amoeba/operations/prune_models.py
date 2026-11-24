"""What ``prune`` returns and how callers hold it (slice 228, D9).

A leaf module: ``Deps`` carries a ``Prune`` and so cannot import ``prune`` itself, which
reads the answering and resume logs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from amoeba.operations.steps.models_runs import OpenRunsReply


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
        self, open_runs: Callable[[], OpenRunsReply], /, *, now: datetime
    ) -> PruneReport:
        """Remove entries older than the hub's ``prune_after_days`` that no open
        question on this machine needs. ``open_runs`` is called only when a walk is
        due, so a quiet machine makes no call for it (262 D12)."""
        ...
