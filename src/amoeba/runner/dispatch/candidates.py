"""Which slices would launch or resume this tick (slice 128, D5). Pure.

``launch_candidates`` is the one definition of the set Observe checks, and the
``decide()`` guard relies on it. It recomputes nothing from the store: it reads the
view's dispatch facts and the checkout holders.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from amoeba.runner.dispatch.checkout import Checkout
from amoeba.runner.dispatch.facts import SliceDispatchFacts
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.launch import text_parameter
from amoeba.store import PARAM_CHECKOUT, JournalEntry, Node

#: The states that continue a run: a PM's resolution, or an automatic retry.
_RESUMING = frozenset({DispatchState.RESUME, DispatchState.AUTO_RESUME})
#: The states that start a pipeline in a checkout no one holds.
_STARTING = frozenset({DispatchState.READY, DispatchState.REISSUE})


@dataclass(frozen=True)
class Candidate:
    """A slice that would launch or resume this tick, and where (D5)."""

    node_id: str
    state: DispatchState
    checkout: Checkout
    slice_index: int
    cf_project_id: str

    @property
    def resume(self) -> bool:
        """Whether this continues a stopped run rather than starting one."""
        return self.state in _RESUMING


def launch_candidates(
    current: Sequence[Node],
    facts: Mapping[str, SliceDispatchFacts],
    holders: Mapping[Path, frozenset[str]],
) -> tuple[Candidate, ...]:
    """The slices Observe checks: those that could launch or resume this tick.

    A candidate is a ``READY`` or ``REISSUE`` slice in a checkout no one holds; or a
    ``RESUME`` or ``AUTO_RESUME`` slice whose checkout is held by no one or only by
    itself. This is the one definition of the set, and the ``decide()`` guard relies
    on it. Nothing is recomputed from the store.
    """
    found: list[Candidate] = []
    for node in current:
        slice_facts = facts.get(node.id)
        if slice_facts is None or not isinstance(slice_facts.checkout, Checkout):
            continue
        checkout = slice_facts.checkout
        if slice_facts.state is DispatchState.REISSUE:
            checkout = _entry_checkout(slice_facts.reissue_of, checkout)
        elif slice_facts.state in _RESUMING:
            checkout = _entry_checkout(slice_facts.continues, checkout)
        held_by = holders.get(checkout.path, frozenset[str]())
        starting = slice_facts.state in _STARTING and not held_by
        resuming = slice_facts.state in _RESUMING and held_by <= {node.id}
        if not (starting or resuming):
            continue
        found.append(
            Candidate(
                node.id,
                slice_facts.state,
                checkout,
                slice_facts.slice_index,
                slice_facts.cf_project_id,
            )
        )
    return tuple(found)


def _entry_checkout(entry: JournalEntry | None, resolved: Checkout) -> Checkout:
    """Where a reissue or resume acts: the checkout its entry recorded.

    The resolved checkout supplies the worktree id when it is the same directory.
    """
    if entry is None:
        raise ValueError("a reissue or resume step has no entry to take its checkout")
    path = Path(text_parameter(entry, PARAM_CHECKOUT))
    return Checkout(path, resolved.worktree_id if path == resolved.path else None)
