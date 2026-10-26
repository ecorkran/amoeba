"""``GateStage``: the tick's gate-related stages, called from ``tick.py`` (slice 128).

``tick.py`` is near its size limit, so what this slice adds to the tick lives here and
``tick.py`` calls it in a few lines. The stage is built in ``ProjectTick.__init__``
beside the act stage. This task adds the outcome stage; the merge observation and the
pre-dispatch reads join it in later tasks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from amoeba.process import RunOutcome
from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfRun
from amoeba.runner.decide import ProjectView
from amoeba.runner.faults import Fault, FaultKind, NodeContext, TickFaults
from amoeba.runner.gates.accepted import (
    AcceptedOutcome,
    accepted_by_pm,
    disagreement_check,
)
from amoeba.runner.gates.dispatch_reads import (
    DispatchReadFailed,
    check_candidate,
    read_dispatch_facts,
)
from amoeba.runner.gates.outcome import (
    OutcomeObservation,
    observe_outcome,
    unobservable,
)
from amoeba.runner.gates.predispatch import (
    EVIDENCE_DISAGREEMENT_CHECK,
    Candidate,
    Disagreement,
    DispatchCheck,
    Ok,
    launch_candidates,
)
from amoeba.runner.lifecycle.steps import STEP_SEQUENCE, LifecycleStep
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
    #: Whether the stage wrote a disagreement check (D7).
    wrote: bool = False


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
        wrote = False
        tree = LifecycleTree(self._store.nodes_for_project(self._project_id))
        for candidate in launch_candidates(
            view.current_steps, view.dispatch, view.checkout_holders
        ):
            self._context.set(candidate.node_id)
            reads = read_dispatch_facts(
                candidate, budget, self._cf_run, self._timeout_seconds
            )
            if reads is None:
                return DispatchStageResult(checks, True, wrote)
            if isinstance(reads, DispatchReadFailed):
                faults.add(_read_failed(candidate, reads))
                continue
            accepted = self._accepted(tree, candidate)
            result = check_candidate(candidate, reads, accepted=accepted is not None)
            if isinstance(result, Disagreement) and accepted is not None:
                result, new = self._record_disagreement(
                    tree, candidate, result, accepted
                )
                wrote = wrote or new
            elif isinstance(result, Disagreement):
                result = result.ok
            if result is not None:
                checks[candidate.node_id] = result
        return DispatchStageResult(checks, False, wrote)

    def _predecessor(self, tree: LifecycleTree, candidate: Candidate) -> Node | None:
        """The node of the step before ``candidate``'s, under the same slice."""
        step_node = tree.node(candidate.node_id)
        slice_node = None if step_node is None else tree.parent(step_node)
        if slice_node is None:
            return None
        before = STEP_SEQUENCE[STEP_SEQUENCE.index(candidate.step) - 1]
        return next(
            (c for c in tree.children(slice_node) if c.cf.phase == before.value), None
        )

    def _accepted(
        self, tree: LifecycleTree, candidate: Candidate
    ) -> AcceptedOutcome | None:
        """Whether the PM accepted the predecessor's completed outcome (D7)."""
        if not candidate.needs_gate:
            return None
        predecessor = self._predecessor(tree, candidate)
        if predecessor is None:
            return None
        entries = self._store.journal_entries(self._project_id, node_id=predecessor.id)
        blocked = self._store.blocked_state_for(predecessor.id, include_resolved=True)
        return accepted_by_pm(entries, blocked)

    def _record_disagreement(
        self,
        tree: LifecycleTree,
        candidate: Candidate,
        disagreement: Disagreement,
        accepted: AcceptedOutcome,
    ) -> tuple[Ok, bool]:
        """Record D7's check on the slice node; dispatch goes on with its id.

        Returns the ``Ok`` naming the check, and whether a record was written.
        """
        predecessor = self._predecessor(tree, candidate)
        step_node = tree.node(candidate.node_id)
        slice_node = None if step_node is None else tree.parent(step_node)
        if predecessor is None or slice_node is None:
            return disagreement.ok, False
        check = disagreement_check(
            accepted,
            slice_node.id,
            LifecycleStep(predecessor.cf.phase),
            disagreement.gate,
            self._amoeba_version,
        )
        new = self._store.check(check.id) is None
        self._store.record_check(check, project_id=self._project_id)
        ok = Ok({**disagreement.ok.evidence, EVIDENCE_DISAGREEMENT_CHECK: check.id})
        return ok, new

    def _observe(
        self, tree: LifecycleTree, observed: ObservedRun, budget: TickBudget
    ) -> OutcomeObservation | None:
        entry = observed.run.entry
        step_node = tree.node(entry.node_id)
        slice_node = None if step_node is None else tree.parent(step_node)
        initiative = None if slice_node is None else tree.parent(slice_node)
        step = None if step_node is None else tree.step_of(step_node)
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
