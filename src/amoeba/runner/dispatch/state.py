"""Where a step is in its dispatch, derived from its own journal entries (D3).

Pure: the caller reads the step's entries (oldest first, a small list bounded by
the attempt limit) and, for a step whose journal says it was pointed, this tick's
read-back answer. Nothing is stored: a step stays ``runnable`` while its run is in
flight, and "in flight" is what 122 defines, an unresolved entry.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from amoeba.store import CommandKind, JournalEntry, JournalOutcome, JournalResolver


class DispatchState(StrEnum):
    """What the planner does for a step, by where its journal says it is."""

    #: Any unresolved entry. Nothing to do.
    IN_FLIGHT = "in_flight"
    #: The latest run's outcome waits for a routing decision. 126 routes it.
    AWAITING_ROUTING = "awaiting_routing"
    #: The latest run never started (recovery resolved it ``not_applied``).
    REISSUE = "reissue"
    #: The pointer write landed and CF still points at the slice: launch.
    POINTED = "pointed"
    #: Anything else: write the pointer.
    NEEDS_POINTER = "needs_pointer"


#: What a pointer write may be resolved as, for the step to count as pointed.
_POINTED_OUTCOMES = frozenset({JournalOutcome.COMPLETED, JournalOutcome.ADOPTED})


def dispatch_state(
    entries: Sequence[JournalEntry], *, pointer_confirmed: bool
) -> DispatchState:
    """The step's state from its ``entries``, oldest first.

    ``pointer_confirmed`` is this tick's read-back: whether CF, read in the checkout
    now, still points at the step's slice. A journal that says pointed with
    ``pointer_confirmed`` false is ``NEEDS_POINTER``: the pointer moved or could not
    be read, so it is written again.
    """
    if any(not entry.is_resolved for entry in entries):
        return DispatchState.IN_FLIGHT
    latest_run = next(
        (e for e in reversed(entries) if e.kind is CommandKind.SQ_RUN), None
    )
    if latest_run is not None and latest_run.awaits_routing:
        return DispatchState.AWAITING_ROUTING
    latest = entries[-1] if entries else None
    if latest is None:
        return DispatchState.NEEDS_POINTER
    if _recovery_found_no_run(latest):
        return DispatchState.REISSUE
    if _pointed(latest) and pointer_confirmed:
        return DispatchState.POINTED
    return DispatchState.NEEDS_POINTER


def _recovery_found_no_run(entry: JournalEntry) -> bool:
    return (
        entry.kind is CommandKind.SQ_RUN
        and entry.outcome is JournalOutcome.NOT_APPLIED
        and entry.resolved_by is JournalResolver.RECOVERY
    )


def _pointed(entry: JournalEntry) -> bool:
    return entry.kind is CommandKind.CF_WRITE and entry.outcome in _POINTED_OUTCOMES
