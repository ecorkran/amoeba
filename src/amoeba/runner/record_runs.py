"""Record the runs the observer found finished (D1, slice 128).

Held apart from ``tick.py`` to keep it short. A finished run is recorded by
``finish.record``; a ``completed`` one only together with its outcome observation. One
the budget cut off before its observation was taken is not recorded: its entry stays
unresolved and tracked, and the run counts as still in flight (D2).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from amoeba.runner import finish
from amoeba.runner.faults import LaunchFailure, NodeContext
from amoeba.runner.gates.outcome_record import OutcomeObservation
from amoeba.runner.gates.stage import completes
from amoeba.runner.launch import LaunchTracker
from amoeba.runner.observed import LaunchFailed, ObservedRun
from amoeba.store import Store


@dataclass(frozen=True)
class RecordedRuns:
    """What recording left: a usage-error message, the runs still in flight, and
    whether anything was written."""

    shape_error: str | None
    pending: tuple[ObservedRun, ...]
    wrote: bool


def record_finished(
    store: Store,
    context: NodeContext,
    tracker: LaunchTracker,
    version_label: str,
    runs: Sequence[ObservedRun],
    observations: Mapping[str, OutcomeObservation],
) -> RecordedRuns:
    """Record each finished run; return what is still pending and any shape error."""
    shape_error: str | None = None
    wrote = False
    pending: list[ObservedRun] = []
    for observed in runs:
        if observed.finished is None:
            pending.append(observed)
            continue
        entry = observed.run.entry
        observation = observations.get(entry.id)
        if completes(observed) and observation is None:
            pending.append(ObservedRun(observed.run))
            continue
        pending.append(observed)
        context.set(entry.node_id)
        finish.record(store, entry, observed.finished, version_label, observation)
        tracker.forget(entry.id)
        wrote = True
        if (
            isinstance(observed.finished, LaunchFailed)
            and observed.finished.failure is LaunchFailure.USAGE_ERROR
        ):
            shape_error = (
                f"`sq run ... --run-id` exited 2 and left no run for entry "
                f"{entry.id}: a shape the Runner needs is missing; "
                f"stderr: {observed.finished.tail}"
            )
    return RecordedRuns(shape_error, tuple(pending), wrote)
