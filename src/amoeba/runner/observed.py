"""What observing an in-flight run can conclude: the value types."""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.process import RunOutcomeDocument
from amoeba.runner.budget import TickResult
from amoeba.runner.decide import InFlightRun
from amoeba.runner.faults import LaunchFailure


@dataclass(frozen=True)
class RunEnded:
    """Squadron reported the run finished (or paused, or orphaned)."""

    document: RunOutcomeDocument


@dataclass(frozen=True)
class RunVanished:
    """A confirmed run now has no state at all."""


@dataclass(frozen=True)
class LaunchFailed:
    """The launch never produced a run. ``tail`` is the stderr tail or the error."""

    failure: LaunchFailure
    exit_code: int | None
    tail: str


type Finished = RunEnded | RunVanished | LaunchFailed


@dataclass(frozen=True)
class ObservedRun:
    """One in-flight run as observed this tick; ``finished`` is set when it ended."""

    run: InFlightRun
    finished: Finished | None = None


@dataclass(frozen=True)
class Observed:
    """The runs observed, and whether the budget let the pass complete."""

    runs: tuple[ObservedRun, ...]
    result: TickResult
