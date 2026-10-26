"""One project's tick: observe, record finished runs, decide, act, close.

The sequence is fixed code (D1): intents are applied first (124), then the PM's
resolutions are answered (127), then the rest.
Slots later slices fill are marked in comments only: the body of
``finish.record`` (125). Routing (126) runs after record, on a view built before it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Final

from amoeba.process import UpstreamShapeError
from amoeba.runner import finish
from amoeba.runner.act import ActStage
from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.cf_call import CfRun
from amoeba.runner.decide import Action, Planner, ProjectView, decide
from amoeba.runner.dispatch.observe_pointer import PointerStage
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.dispatch.pointer_watch import watch_pointers
from amoeba.runner.faults import (
    RUNNER_ACTOR,
    LaunchFailure,
    NodeContext,
    TickFaults,
    raise_expected_faults,
)
from amoeba.runner.gates.outcome import OutcomeObservation
from amoeba.runner.gates.stage import GateStage, completes
from amoeba.runner.intent.apply import apply_pending_intents
from amoeba.runner.intent.governance import DesiredStateIndex
from amoeba.runner.launch import LaunchTracker, PopenFactory
from amoeba.runner.lifecycle.plan_stage import PlanStage
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.observe import RunObserver
from amoeba.runner.observe_resume import resumed_from_pauses
from amoeba.runner.observed import LaunchFailed, ObservedRun
from amoeba.runner.probes import LinkProbes
from amoeba.runner.project_config import ProjectSettings
from amoeba.runner.project_view import build_project_view
from amoeba.runner.resolutions.stage import apply_pending_resolutions
from amoeba.runner.routing.overrun import watch_overruns
from amoeba.runner.routing.stage import route_outcomes
from amoeba.runner.routing.table import RoutingTable
from amoeba.store import CommandKind, JournalEntry, Store


@dataclass(frozen=True)
class RecordedRuns:
    """What recording left: a usage-error message, and the runs still in flight."""

    shape_error: str | None
    pending: tuple[ObservedRun, ...]


#: Who closes a project escalation that stopped recurring.
CLOSED_BY: Final = RUNNER_ACTOR


class ProjectTick:
    """Runs one project through one tick. Built fresh for each tick."""

    def __init__(
        self,
        *,
        project_id: str,
        store: Store,
        supervisor_dir: Path,
        planners: Sequence[Planner],
        observer: RunObserver,
        probes: LinkProbes,
        plans: PlanStage,
        pointers: PointerStage,
        tracker: LaunchTracker,
        popen: PopenFactory,
        now: Callable[[], datetime],
        context: NodeContext,
        version_label: str,
        routing_table: RoutingTable,
        project_settings: ProjectSettings,
        cf_run: CfRun,
        call_timeout_seconds: float,
        amoeba_version: str,
    ) -> None:
        self._project_id = project_id
        self._version_label = version_label
        self._routing_table = routing_table
        self._project_settings = project_settings
        self._amoeba_version = amoeba_version
        self._store = store
        self._planners = planners
        self._observer = observer
        self._probes = probes
        self._plans = plans
        self._pointers = pointers
        self._pointer_confirmed: frozenset[str] = frozenset()
        self._dispatching = any(isinstance(p, DispatchPlanner) for p in planners)
        self._tracker = tracker
        self._now = now
        self._context = context
        self._act = ActStage(
            store=store,
            supervisor_dir=supervisor_dir,
            pointers=pointers,
            poll_run=observer.poll_run,
            tracker=tracker,
            popen=popen,
            now=now,
            context=context,
            version_label=version_label,
        )
        self._gates = GateStage(
            store=store,
            project_id=project_id,
            context=context,
            cf_run=cf_run,
            call_timeout_seconds=call_timeout_seconds,
            amoeba_version=amoeba_version,
        )
        self.wrote = False
        """Whether this tick wrote to the store or issued a command."""

    def run(self, budget: TickBudget) -> TickResult:
        """Run the stages in order; ``CUT_OFF`` when the budget ran out."""
        faults = TickFaults()
        desired = self._apply_intents()
        self._answer_resolutions()
        # Observe is not filtered by hold or drive. Slices 125 and 128 read
        # ``desired.drives_anything()`` to scope their Observe work.
        entries = self._run_entries()
        observed = self._observer.observe(
            entries,
            budget,
            faults,
            self._context,
            resumed_from_pauses(self._store, entries),
        )
        # [reconciliation reads - slice 123: the plan stage, after the probes]
        links = [link.cf_project_id for link in self._store.cf_links(self._project_id)]
        probed = observed.result
        if probed is TickResult.COMPLETE:
            probed = self._probes.check(links, budget, faults, self._project_id)
        if probed is TickResult.COMPLETE:
            probed = self._plan_reads(links, budget, faults)
        # A completed run is recorded only with its outcome observation. One the
        # budget cut off stays unresolved and tracked, and is observed next tick.
        outcomes = self._gates.observe_outcomes(observed.runs, budget)
        runs = self._record_finished(observed.runs, outcomes.observations)
        shape_error = runs.shape_error
        in_flight = [o.run.entry for o in runs.pending if o.finished is None]
        watch_pointers(self._store, self._project_id, in_flight, faults)
        # Beside the pointer watch, before the faults are raised, so the existing
        # raise path records the overrun (slice 126, D7). It reads only in-flight
        # entries, which routing never touches, so its place changes no result.
        watch_overruns(in_flight, self._routing_table, self._now(), faults)
        self.wrote = (
            raise_expected_faults(self._store, self._project_id, faults) or self.wrote
        )
        if shape_error is not None:
            raise UpstreamShapeError(shape_error)
        if probed is TickResult.CUT_OFF:
            return TickResult.CUT_OFF
        pointed = self._pointers.observe_project(
            self._store, self._project_id, desired, budget, self._context
        )
        self.wrote = pointed.wrote or self.wrote
        if pointed.result is TickResult.CUT_OFF:
            return TickResult.CUT_OFF
        self._pointer_confirmed = pointed.confirmed
        # The view is built before routing: what routing does is first seen by the
        # next tick's view (slice 126, D8).
        # Reads, and the completion write of a merge git shows done; before the view.
        merges = self._gates.observe_merges(desired, budget, faults)
        self.wrote = merges.wrote or self.wrote
        view = self._build_view(runs.pending, self._probes.results(links), desired)
        # Reads only, so a cut-off just defers them: a candidate with no result
        # cannot launch this tick (D5).
        dispatch = self._gates.check_dispatch(view, budget, faults)
        view = replace(
            view,
            dispatch_checks=dispatch.checks,
            merge_observations=merges.observations,
        )
        self.wrote = dispatch.wrote or self.wrote
        # Store reads and writes only, so no budget check: it starts no subprocess.
        self.wrote = (
            route_outcomes(
                self._store,
                self._project_id,
                self._routing_table,
                self._amoeba_version,
                self._context,
            )
            or self.wrote
        )
        decided = self._decide(view)
        acted = self._act.run(decided, budget, faults)
        self.wrote = acted.wrote or self.wrote
        # Faults the act stage met (a failed continuation pre-poll) are raised here;
        # the store deduplicates, so the kinds raised above write nothing twice.
        self.wrote = (
            raise_expected_faults(self._store, self._project_id, faults) or self.wrote
        )
        if acted.result is TickResult.CUT_OFF or dispatch.cut_off or merges.cut_off:
            return TickResult.CUT_OFF
        self._close_recovered(faults)
        return TickResult.COMPLETE

    def _apply_intents(self) -> DesiredStateIndex:
        """Apply pending intents, then read the desired state once for this tick.

        Store-only and independent of link state, so a PM's pause lands even when
        CF is down. The context is cleared: an exception here is about the project,
        not a node. The index is never cached across ticks.
        """
        self._context.clear()
        applied = apply_pending_intents(self._store, self._project_id)
        self.wrote = applied > 0 or self.wrote
        return DesiredStateIndex(self._store.desired_states(self._project_id))

    def _answer_resolutions(self) -> None:
        """Answer the PM's pending resolutions, before anything reads the nodes.

        Store reads and writes only, so no budget check: it starts no subprocess.
        It runs before Observe and the view so no planner or route sees a node
        whose resolution has not been acknowledged (slice 127, D1). The context is
        cleared afterwards: an exception past this stage is not about that node.
        """
        tree = LifecycleTree(self._store.nodes_for_project(self._project_id))
        answered = apply_pending_resolutions(
            self._store, self._project_id, tree, self._context
        )
        self._context.clear()
        self.wrote = answered or self.wrote

    def _plan_reads(
        self, links: Sequence[str], budget: TickBudget, faults: TickFaults
    ) -> TickResult:
        """Read and reconcile each due link whose probe passed (D7).

        An exception here is not about any node: the context is cleared so the
        tenant's catch raises a project-scoped fault, and the link is left due
        because it was never recorded complete (D5).
        """
        self._context.clear()
        result, wrote = self._plans.run(
            self._store,
            self._project_id,
            links,
            self._probes.results(links),
            budget,
            faults,
        )
        self.wrote = wrote or self.wrote
        return result

    def _run_entries(self) -> list[JournalEntry]:
        return [
            entry
            for entry in self._store.unresolved_journal_entries(self._project_id)
            if entry.kind is CommandKind.SQ_RUN
        ]

    def _record_finished(
        self,
        runs: Sequence[ObservedRun],
        observations: Mapping[str, OutcomeObservation],
    ) -> RecordedRuns:
        """Record each finished run. Returns what is still pending, and any shape error.

        A completed run with no observation (the budget cut it off) is not recorded:
        it stays unresolved and tracked, and counts as still in flight.
        """
        shape_error: str | None = None
        pending: list[ObservedRun] = []
        for observed in runs:
            if observed.finished is None:
                pending.append(observed)
                continue
            entry = observed.run.entry
            observation = observations.get(entry.id)
            if completes(observed) and observation is None:
                pending.append(ObservedRun(observed.run))
                continue
            pending.append(observed)
            self._context.set(entry.node_id)
            finish.record(
                self._store,
                entry,
                observed.finished,
                self._version_label,
                observation,
            )
            self._tracker.forget(entry.id)
            self.wrote = True
            if (
                isinstance(observed.finished, LaunchFailed)
                and observed.finished.failure is LaunchFailure.USAGE_ERROR
            ):
                shape_error = (
                    f"`sq run ... --run-id` exited 2 and left no run for entry "
                    f"{entry.id}: a shape the Runner needs is missing; "
                    f"stderr: {observed.finished.tail}"
                )
        return RecordedRuns(shape_error, tuple(pending))

    def _build_view(
        self,
        runs: Sequence[ObservedRun],
        link_probes: Mapping[str, bool],
        desired: DesiredStateIndex,
    ) -> ProjectView:
        self._context.clear()
        built = build_project_view(
            self._store,
            self._project_id,
            self._now(),
            runs,
            link_probes,
            desired,
            dispatching=self._dispatching,
            pointer_confirmed=self._pointer_confirmed,
            merge_policy=self._project_settings.merge_policy,
        )
        self.wrote = built.wrote or self.wrote
        return built.view

    def _decide(self, view: ProjectView) -> list[Action]:
        self._context.clear()
        return list(decide(view, self._planners))

    def _close_recovered(self, faults: TickFaults) -> None:
        """Close each open project escalation whose kind did not recur."""
        recurring = {kind.value for kind in faults.kinds()}
        for message in self._store.open_project_escalations(self._project_id):
            if message.fault_kind not in recurring:
                self._store.close_project_escalation(message.id, closed_by=CLOSED_BY)
                self.wrote = True
