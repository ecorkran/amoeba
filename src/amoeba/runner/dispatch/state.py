"""Where a step is in its dispatch, derived from its own journal entries (D3).

Pure: the caller reads the step's entries (oldest first, a small list bounded by
the attempt limit) and, for a step whose journal says it was pointed, this tick's
read-back answer. Nothing is stored: a step stays ``runnable`` while its run is in
flight, and "in flight" is what 122 defines, an unresolved entry.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from amoeba.runner.observed import RunEnded
from amoeba.runner.resolutions.vocabulary import ResolutionDecision
from amoeba.runner.supervise import (
    OutcomeClass,
    classify,
    recorded_document,
    run_to_resume,
)
from amoeba.store import (
    PARAM_RESOLUTION,
    BlockedState,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
    ResolutionOutcome,
)


class DispatchState(StrEnum):
    """What the planner does for a step, by where its journal says it is."""

    #: Any unresolved entry. Nothing to do.
    IN_FLIGHT = "in_flight"
    #: The latest run never started (recovery resolved it ``not_applied``).
    REISSUE = "reissue"
    #: The pointer write landed and CF still points at the slice: launch.
    POINTED = "pointed"
    #: Anything else: write the pointer.
    NEEDS_POINTER = "needs_pointer"
    #: An applied ``resume`` nobody has carried out, with a run to resume.
    RESUME = "resume"
    #: The latest run ended in a transient way (D4): resume it, within the bound.
    AUTO_RESUME = "auto_resume"


#: What a pointer write may be resolved as, for the step to count as pointed.
_POINTED_OUTCOMES = frozenset({JournalOutcome.COMPLETED, JournalOutcome.ADOPTED})


def dispatch_state(
    entries: Sequence[JournalEntry],
    resolution: BlockedState | None,
    *,
    pointer_confirmed: bool,
) -> DispatchState:
    """The step's state from its ``entries``, oldest first, and its ``resolution``.

    ``resolution`` is the step's latest acknowledged-applied resolution with a
    decision, or ``None``. While no entry names it in ``PARAM_RESOLUTION`` it has
    not been carried out, and it decides (D5); this is a reference, not a time
    comparison. ``accept`` of a completed outcome and ``stop`` leave the step done
    or blocked, so they never reach here as a state.

    ``pointer_confirmed`` is this tick's read-back: whether CF, read in the checkout
    now, still points at the step's slice. A journal that says pointed with
    ``pointer_confirmed`` false is ``NEEDS_POINTER``: the pointer moved or could not
    be read, so it is written again.
    """
    if any(not entry.is_resolved for entry in entries):
        return DispatchState.IN_FLIGHT
    pending = _pending_resume(entries, resolution)
    if pending is not None:
        return pending
    latest = entries[-1] if entries else None
    if latest is None:
        return DispatchState.NEEDS_POINTER
    if _ended_transiently(latest):
        return DispatchState.AUTO_RESUME
    if _recovery_found_no_run(latest):
        return DispatchState.REISSUE
    if _pointed(latest) and pointer_confirmed:
        return DispatchState.POINTED
    return DispatchState.NEEDS_POINTER


def _pending_resume(
    entries: Sequence[JournalEntry], resolution: BlockedState | None
) -> DispatchState | None:
    """``RESUME`` for an applied ``resume`` nobody has carried out, or ``None``.

    A ``resume`` with no run to resume sets no state: the block is resolved and the
    step is launched afresh by its ordinary state (D6).
    """
    if resolution is None or resolution.resolution is None:
        return None
    if resolution.runner_outcome is not ResolutionOutcome.APPLIED:
        return None
    if resolution.resolution.decision != ResolutionDecision.RESUME.value:
        return None
    if any(
        entry.parameters.get(PARAM_RESOLUTION) == resolution.id for entry in entries
    ):
        return None
    return DispatchState.RESUME if run_to_resume(entries) is not None else None


def _ended_transiently(entry: JournalEntry) -> bool:
    """Whether this is a run entry whose recorded outcome the supervisor resumes.

    A node that is blocked is not current, so it never reaches here: a transient
    outcome at the bound blocks instead (D5).
    """
    if entry.kind is not CommandKind.SQ_RUN:
        return False
    document = recorded_document(entry)
    return (
        document is not None and classify(RunEnded(document)) is OutcomeClass.TRANSIENT
    )


def _recovery_found_no_run(entry: JournalEntry) -> bool:
    return (
        entry.kind is CommandKind.SQ_RUN
        and entry.outcome is JournalOutcome.NOT_APPLIED
        and entry.resolved_by is JournalResolver.RECOVERY
    )


def _pointed(entry: JournalEntry) -> bool:
    return entry.kind is CommandKind.CF_WRITE and entry.outcome in _POINTED_OUTCOMES
