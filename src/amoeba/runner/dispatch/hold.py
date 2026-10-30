"""Which checkouts are held (D4): one pipeline per checkout, from the pointer write.

A checkout is held while any of these is true:

- an unresolved ``sq_run`` entry in the project has that checkout;
- a node that is not ``done`` has a latest ``sq_run`` entry with that checkout whose
  recorded outcome is ``paused``, ``failed`` or ``orphaned`` (a stopped run still has
  its branch checked out and may be resumed; the rule reads the run's recorded
  outcome, never the block kind, so a stopped run that is blocked on ``HUMAN`` still
  holds it until the block is released);
- a current step in that checkout is ``POINTED``, or has an unresolved pointer write
  in flight: its claim starts with the pointer write.

Computed across the whole project, not only over current steps: a held or excluded
slice's run in flight or paused still holds its checkout. A pointer claim lapses when
its step stops being current, because only current steps are looked at.

Pure: the caller reads the entries and the facts.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Final

from amoeba.process import RunOutcome
from amoeba.runner.dispatch.checkout import Checkout
from amoeba.runner.dispatch.facts import StepDispatchFacts
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.ingest.record import RESULT_OUTCOME
from amoeba.store import PARAM_CHECKOUT, CommandKind, JournalEntry


def checkout_holders(
    entries: Sequence[JournalEntry],
    done_node_ids: Collection[str],
    current: Mapping[str, StepDispatchFacts],
) -> Mapping[Path, frozenset[str]]:
    """Each held checkout, with the ids of the nodes that hold it.

    ``entries`` are the project's journal entries, oldest first. ``done_node_ids``
    are the nodes that are ``done``. ``current`` is the dispatch facts of the
    current pipeline steps, by node id. Naming the holders lets a step's own
    continuation act in a checkout held only by itself (slice 127, D5).
    """
    holders: dict[Path, set[str]] = {}
    latest_run: dict[str, JournalEntry] = {}
    for entry in entries:
        checkout = _checkout_of(entry)
        if checkout is None:
            continue
        if entry.kind is CommandKind.SQ_RUN:
            latest_run[entry.node_id] = entry
            if not entry.is_resolved:
                holders.setdefault(checkout, set()).add(entry.node_id)
        elif not entry.is_resolved and _claimant_is_current(entry, current):
            holders.setdefault(checkout, set()).add(entry.node_id)
    for node_id, entry in latest_run.items():
        checkout = _checkout_of(entry)
        if checkout is not None and node_id not in done_node_ids and _stopped(entry):
            holders.setdefault(checkout, set()).add(node_id)
    for node_id, facts in current.items():
        if facts.state is DispatchState.POINTED and isinstance(
            facts.checkout, Checkout
        ):
            holders.setdefault(facts.checkout.path, set()).add(node_id)
    return {path: frozenset(nodes) for path, nodes in holders.items()}


def _checkout_of(entry: JournalEntry) -> Path | None:
    value = entry.parameters.get(PARAM_CHECKOUT)
    return Path(value) if isinstance(value, str) and value else None


def _claimant_is_current(
    entry: JournalEntry, current: Mapping[str, StepDispatchFacts]
) -> bool:
    """An unresolved pointer write holds its checkout only while its step is current."""
    return entry.node_id in current


#: The recorded outcomes of a run that stopped but can be resumed, so keeps its tree.
_STOPPED_OUTCOMES: Final = frozenset(
    {RunOutcome.PAUSED.value, RunOutcome.FAILED.value, RunOutcome.ORPHANED.value}
)


def _stopped(entry: JournalEntry) -> bool:
    """Whether the run's recorded outcome is ``paused``, ``failed`` or ``orphaned``."""
    return (
        entry.is_resolved
        and entry.result is not None
        and entry.result.get(RESULT_OUTCOME) in _STOPPED_OUTCOMES
    )
