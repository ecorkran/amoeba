"""``GateStage``: the tick's gate-related stages, called from ``tick.py`` (slice 128).

``tick.py`` is near its size limit, so what this slice adds to the tick lives here and
``tick.py`` calls it in a few lines. The stage is built in ``ProjectTick.__init__``
beside the act stage. It holds the outcome stage (D2), the merge observation (D9) and
the pre-dispatch reads (D5).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from amoeba.process import RunOutcome
from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfRun
from amoeba.runner.decide import ProjectView
from amoeba.runner.faults import Fault, FaultKind, NodeContext, TickFaults
from amoeba.runner.gates.candidates import Candidate, launch_candidates
from amoeba.runner.gates.dispatch_reads import (
    DispatchReadFailed,
    check_candidate,
    read_dispatch_facts,
)
from amoeba.runner.gates.outcome import observe_outcome
from amoeba.runner.gates.outcome_record import OutcomeObservation, unobservable
from amoeba.runner.gates.predispatch import (
    DispatchCheck,
)
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.observed import ObservedRun, RunEnded
from amoeba.store import Node, Store


@dataclass(frozen=True)
class DispatchStageResult:
    """The pre-dispatch results by node id, and whether the budget cut the pass short.

    A candidate with no entry has no result: its reads failed or were cut off.
    """

    checks: Mapping[str, DispatchCheck]
    cut_off: bool


@dataclass(frozen=True)
class OutcomeStageResult:
    """The observations taken by entry id, and whether the budget cut the pass short."""

    observations: Mapping[str, OutcomeObservation]
    cut_off: bool


def completes(observed: ObservedRun) -> bool:
    """Whether the run ended with a ``completed`` outcome (the only kind observed)."""
    finished = observed.finished
    return (
        isinstance(finished, RunEnded)
        and finished.document.outcome is RunOutcome.COMPLETED
    )


@dataclass(frozen=True)
class _Lineage:
    """A step node and the slice and initiative above it; ``None`` where absent."""

    step: Node | None
    slice_node: Node | None
    initiative: Node | None


def _lineage(tree: LifecycleTree, node_id: str) -> _Lineage:
    step = tree.node(node_id)
    slice_node = None if step is None else tree.parent(step)
    initiative = None if slice_node is None else tree.parent(slice_node)
    return _Lineage(step, slice_node, initiative)


class GateStage:
    """Reads CF's gate, the design and git around the runs of one project."""

    def __init__(
        self,
        *,
        store: Store,
        project_id: str,
        context: NodeContext,
        cf_run: CfRun,
        call_timeout_seconds: float,
        amoeba_version: str,
    ) -> None:
        self._store = store
        self._project_id = project_id
        self._context = context
        self._cf_run = cf_run
        self._timeout_seconds = call_timeout_seconds
        self._amoeba_version = amoeba_version

    def observe_outcomes(
        self, runs: Sequence[ObservedRun], budget: TickBudget
    ) -> OutcomeStageResult:
        """Observe each finished ``completed`` run (D2), until the budget runs out.

        A run whose observation was cut off has no entry in the result, so the tick
        leaves its entry unresolved and the next tick observes it again.
        """
        completed = [observed for observed in runs if completes(observed)]
        if not completed:
            return OutcomeStageResult({}, False)
        tree = LifecycleTree(self._store.nodes_for_project(self._project_id))
        observations: dict[str, OutcomeObservation] = {}
        for observed in completed:
            entry = observed.run.entry
            self._context.set(entry.node_id)
            observation = self._observe(tree, observed, budget)
            if observation is None:
                return OutcomeStageResult(observations, True)
            observations[entry.id] = observation
        return OutcomeStageResult(observations, False)

    def check_dispatch(
        self, view: ProjectView, budget: TickBudget, faults: TickFaults
    ) -> DispatchStageResult:
        """Read and check every launch or resume candidate (D5), until the budget ends.

        A read that fails adds a project-scoped ``checkout_read_failed`` fault and
        gives the candidate no result: the step is not blocked, because it is not at
        fault. A candidate the budget cut off also has no result; the tick then ends
        as cut off so the closure waits for a complete tick.
        """
        checks: dict[str, DispatchCheck] = {}
        for candidate in launch_candidates(
            view.current_slices, view.dispatch, view.checkout_holders
        ):
            self._context.set(candidate.node_id)
            reads = read_dispatch_facts(
                candidate, budget, self._cf_run, self._timeout_seconds
            )
            if reads is None:
                return DispatchStageResult(checks, True)
            if isinstance(reads, DispatchReadFailed):
                faults.add(_read_failed(candidate, reads))
                continue
            checks[candidate.node_id] = check_candidate(candidate, reads)
        return DispatchStageResult(checks, False)

    def _observe(
        self, tree: LifecycleTree, observed: ObservedRun, budget: TickBudget
    ) -> OutcomeObservation | None:
        entry = observed.run.entry
        lineage = _lineage(tree, entry.node_id)
        slice_node, initiative = lineage.slice_node, lineage.initiative
        step = None if lineage.step is None else tree.step_of(lineage.step)
        if step is None or slice_node is None or initiative is None:
            reason = f"the node of entry {entry.id} is not a step of a slice"
            return unobservable(entry, entry.node_id, reason, self._amoeba_version)
        if initiative.cf.index is None:
            reason = f"initiative {initiative.id} carries no CF index"
            return unobservable(entry, slice_node.id, reason, self._amoeba_version)
        return observe_outcome(
            entry,
            step,
            slice_node,
            initiative.cf.index,
            budget,
            self._cf_run,
            self._timeout_seconds,
            self._amoeba_version,
        )


def _read_failed(candidate: Candidate, failed: DispatchReadFailed) -> Fault:
    return Fault(
        FaultKind.CHECKOUT_READ_FAILED,
        f"{failed.command} gave no usable answer in {candidate.checkout.path}: "
        f"{failed.reason}",
        node_id=candidate.node_id,
        extra={
            "checkout": str(candidate.checkout.path),
            "command": failed.command,
            "reason": failed.reason,
        },
    )
