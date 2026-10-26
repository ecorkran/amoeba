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
from amoeba.runner.faults import NodeContext
from amoeba.runner.gates.outcome import (
    OutcomeObservation,
    observe_outcome,
    unobservable,
)
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.observed import ObservedRun, RunEnded
from amoeba.store import Store


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
