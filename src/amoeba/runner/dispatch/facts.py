"""What the planner is told about a current pipeline step (D3, D4, D5).

Built per tick, outside the planner, from the store and the observed snapshot, so
the planner stays pure. One frozen record per step, keyed by node id in the view.
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.runner.dispatch.checkout import Checkout, CheckoutUnresolved
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import BlockedState, JournalEntry

#: ``(initiative index, slice index, step rank)``: which step goes first when a
#: checkout is free for one.
type SortKey = tuple[int, int, int]


@dataclass(frozen=True)
class StepDispatchFacts:
    """One current pipeline step's dispatch facts for this tick."""

    step: LifecycleStep
    state: DispatchState
    checkout: Checkout | CheckoutUnresolved
    slice_index: int
    cf_project_id: str
    sort_key: SortKey
    #: The entry a reissue repeats: the latest ``sq_run`` entry. Set only for
    #: ``REISSUE``.
    reissue_of: JournalEntry | None = None
    #: The latest applied resolution with a decision (slice 127), whether or not it
    #: has been carried out; the planner acts on it only in ``RESUME``, ``REOBSERVE``
    #: and a ``rerun``'s ``NEEDS_POINTER``.
    resolution: BlockedState | None = None
    #: The latest ``sq_run`` entry, whose run a ``RESUME`` or ``REOBSERVE`` continues.
    continues: JournalEntry | None = None
