"""What the planner is told about a current slice (D3, D4, D5).

Built per tick, outside the planner, from the store and the observed snapshot, so
the planner stays pure. One frozen record per slice, keyed by node id in the view.
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.runner.dispatch.checkout import Checkout, CheckoutUnresolved
from amoeba.runner.dispatch.state import DispatchState
from amoeba.store import BlockedState, JournalEntry

#: ``(initiative index, slice index)``: which slice goes first when a checkout is
#: free for one.
type SortKey = tuple[int, int]


@dataclass(frozen=True)
class SliceDispatchFacts:
    """One current slice's dispatch facts for this tick."""

    state: DispatchState
    checkout: Checkout | CheckoutUnresolved
    slice_index: int
    cf_project_id: str
    sort_key: SortKey
    #: The entry a reissue repeats: the latest ``sq_run`` entry. Set only for
    #: ``REISSUE``.
    reissue_of: JournalEntry | None = None
    #: The latest applied resolution with a decision (slice 127), whether or not it
    #: has been carried out; the planner acts on it only in ``RESUME``.
    resolution: BlockedState | None = None
    #: The latest ``sq_run`` entry, whose run a ``RESUME`` or ``AUTO_RESUME`` continues.
    continues: JournalEntry | None = None
