"""The value types of a merge observation (slice 128, D9).

Held apart from ``merge.py`` so the view and the human-step planner can name them
without importing the reads, whose imports reach back to ``decide.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Merged:
    """The recorded head is reachable from the target."""

    head: str


@dataclass(frozen=True)
class NotMerged:
    """The recorded head is not reachable from the target yet."""


@dataclass(frozen=True)
class Unobservable:
    """A merge cannot be observed in git, for ``reason``; a person must look."""

    reason: str


type MergeObservation = Merged | NotMerged | Unobservable
