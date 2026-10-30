"""Build the per-tick dispatch facts for the decide stage (D1, D3, D4).

For each current pipeline step: its own journal entries, its slice's latest observed
CF snapshot, the checkout that owns the slice, and the resulting dispatch state. And,
across the whole project, the checkouts already held. Built each tick from the store
and never cached: nothing here is state.

A step whose slice no checkout can be named for is reported, not guessed at; the tick
blocks it on a human (:func:`block_unresolved`) and the step gets no action.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from amoeba.runner.dispatch.checkout import CheckoutUnresolved, resolve_checkout
from amoeba.runner.dispatch.facts import StepDispatchFacts
from amoeba.runner.dispatch.hold import checkout_holders
from amoeba.runner.dispatch.state import DispatchState, dispatch_state
from amoeba.runner.faults import PAYLOAD_FAULT_KIND, FaultKind
from amoeba.runner.ingest.outcome import PAYLOAD_REASON, BlockPlan, cut_to_bound
from amoeba.runner.ingest.record import block_once
from amoeba.runner.lifecycle.steps import STEP_MAP, Executor, step_rank
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import (
    BlockedKind,
    BlockedState,
    CFSnapshot,
    Node,
    NodeKind,
    NodeStatus,
    ResolutionOutcome,
    Store,
    latest_run_entry,
)

#: A block's payload key for the slice index the checkout could not be found for.
PAYLOAD_INDEX = "index"


@dataclass(frozen=True)
class UnresolvedStep:
    """A current step whose slice has no resolvable checkout."""

    node_id: str
    slice_index: int
    reason: str


@dataclass(frozen=True)
class DispatchView:
    """What the view carries for dispatch."""

    facts: Mapping[str, StepDispatchFacts]
    holders: Mapping[Path, frozenset[str]]
    unresolved: tuple[UnresolvedStep, ...]


#: The states that launch or resume a run, so need a checkout to act.
_NEEDS_CHECKOUT: Final = frozenset(
    {
        DispatchState.READY,
        DispatchState.REISSUE,
        DispatchState.RESUME,
        DispatchState.AUTO_RESUME,
    }
)

#: The states that continue the step's latest run rather than start one.
_CONTINUING: Final = frozenset({DispatchState.RESUME, DispatchState.AUTO_RESUME})


def build_dispatch_view(
    store: Store,
    project_id: str,
    tree: LifecycleTree,
    current: Sequence[Node],
    *,
    is_dir: Callable[[Path], bool],
) -> DispatchView:
    """The dispatch facts of ``current``'s pipeline steps, and the held checkouts."""
    observed: dict[str, CFSnapshot | None] = {}
    facts: dict[str, StepDispatchFacts] = {}
    unresolved: list[UnresolvedStep] = []
    for node in current:
        found = _facts_for(store, project_id, tree, node, observed, is_dir)
        if found is None:
            continue
        facts[node.id] = found
        if isinstance(found.checkout, CheckoutUnresolved) and (
            found.state in _NEEDS_CHECKOUT
        ):
            unresolved.append(
                UnresolvedStep(node.id, found.slice_index, found.checkout.reason)
            )
    entries = store.journal_entries(project_id)
    done = {n.id for n in tree.nodes if n.status is NodeStatus.DONE}
    holders = checkout_holders(entries, done)
    return DispatchView(facts, holders, tuple(unresolved))


def block_unresolved(store: Store, unresolved: Sequence[UnresolvedStep]) -> bool:
    """Block each unresolved step on a human (122's node block). Returns whether any."""
    for step in unresolved:
        reason = cut_to_bound(step.reason)
        block_once(
            store,
            step.node_id,
            BlockPlan(
                BlockedKind.HUMAN,
                f"no checkout for slice index {step.slice_index}: {reason}",
                {
                    PAYLOAD_FAULT_KIND: FaultKind.CHECKOUT_UNRESOLVED.value,
                    PAYLOAD_INDEX: step.slice_index,
                    PAYLOAD_REASON: reason,
                },
            ),
        )
    return bool(unresolved)


def _facts_for(
    store: Store,
    project_id: str,
    tree: LifecycleTree,
    node: Node,
    observed: dict[str, CFSnapshot | None],
    is_dir: Callable[[Path], bool],
) -> StepDispatchFacts | None:
    step = tree.step_of(node)
    if step is None or STEP_MAP[step].executor is not Executor.PIPELINE:
        return None
    slice_node = tree.parent(node)
    if slice_node is None or slice_node.kind is not NodeKind.SLICE:
        return None
    index, cf_project = slice_node.cf.index, slice_node.cf.project
    initiative = tree.parent(slice_node)
    if index is None or cf_project is None or initiative is None:
        return None
    if initiative.cf.index is None:
        return None
    if cf_project not in observed:
        observed[cf_project] = store.latest_cf_snapshots(project_id, cf_project)[1]
    entries = store.journal_entries(project_id, node_id=node.id)
    resolution = _applied_resolution(store, node.id)
    state = dispatch_state(entries, resolution)
    return StepDispatchFacts(
        step=step,
        state=state,
        checkout=resolve_checkout(observed[cf_project], index, is_dir=is_dir),
        slice_index=index,
        cf_project_id=cf_project,
        sort_key=(initiative.cf.index, index, step_rank(step)),
        reissue_of=latest_run_entry(entries)
        if state is DispatchState.REISSUE
        else None,
        resolution=resolution,
        continues=latest_run_entry(entries) if state in _CONTINUING else None,
    )


def _applied_resolution(store: Store, node_id: str) -> BlockedState | None:
    """The step's latest blocked state, if the Runner applied a decision on it."""
    latest = store.blocked_state_for(node_id, include_resolved=True)
    if (
        latest is None
        or latest.runner_outcome is not ResolutionOutcome.APPLIED
        or latest.resolution is None
        or latest.resolution.decision is None
    ):
        return None
    return latest
