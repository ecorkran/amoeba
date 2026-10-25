"""What observing an in-flight run can conclude: the value types."""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.process import RunOutcomeDocument
from amoeba.runner.budget import TickResult
from amoeba.runner.decide import InFlightRun
from amoeba.runner.faults import LaunchFailure, ResumeFailure


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


@dataclass(frozen=True)
class ResumeFailed:
    """A resume that did not take (slice 127, D6).

    ``document`` is the last poll of the run, or ``None`` if there was none. The run
    itself is still where the poll left it, which is why a failed resume keeps the
    run's checkout held and its outcome ``paused``.
    """

    failure: ResumeFailure
    exit_code: int | None
    tail: str
    document: RunOutcomeDocument | None


type Finished = RunEnded | RunVanished | LaunchFailed | ResumeFailed


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
