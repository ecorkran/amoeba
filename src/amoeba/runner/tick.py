"""One project's tick: observe, record finished runs, decide, act, close.

The sequence is fixed code (D1): intents are applied first (124), then the rest.
Slots later slices fill are marked in comments only: the body of
``finish.record`` (125), routing (126) after record.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Final

from amoeba.process import UpstreamShapeError
from amoeba.runner import finish
from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.decide import (
    Action,
    BlockHumanStep,
    LaunchRun,
    Planner,
    ProjectView,
    WriteSlicePointer,
    decide,
)
from amoeba.runner.dispatch.build_view import (
    DispatchView,
    block_unresolved,
    build_dispatch_view,
)
from amoeba.runner.dispatch.observe_pointer import PointerStage
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.dispatch.pointer_watch import watch_pointers
from amoeba.runner.dispatch.reissue import ReissueLaunch, begin_reissue
from amoeba.runner.faults import (
    RUNNER_ACTOR,
    LaunchFailure,
    NodeContext,
    TickFaults,
    raise_expected_faults,
)
from amoeba.runner.intent.apply import apply_pending_intents
from amoeba.runner.intent.governance import DesiredStateIndex, current_steps
from amoeba.runner.launch import (
    PARAM_PARAMS,
    PARAM_PIPELINE,
    LaunchError,
    LaunchTracker,
    PopenFactory,
    build_argv,
    launch,
    mint_run_id,
)
from amoeba.runner.lifecycle.human_steps import block_human_step
from amoeba.runner.lifecycle.plan_stage import PlanStage
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.observe import RunObserver
from amoeba.runner.observed import LaunchFailed, ObservedRun
from amoeba.runner.probes import LinkProbes
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_RUN_ID,
    CommandKind,
    JournalEntry,
    Node,
    Store,
)

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
    ) -> None:
        self._project_id = project_id
        self._version_label = version_label
        self._store = store
        self._supervisor_dir = supervisor_dir
        self._planners = planners
        self._observer = observer
        self._probes = probes
        self._plans = plans
        self._pointers = pointers
        self._pointer_confirmed: frozenset[str] = frozenset()
        self._dispatching = any(isinstance(p, DispatchPlanner) for p in planners)
        self._tracker = tracker
        self._popen = popen
        self._now = now
        self._context = context
        self.wrote = False
        """Whether this tick wrote to the store or issued a command."""

    def run(self, budget: TickBudget) -> TickResult:
        """Run the stages in order; ``CUT_OFF`` when the budget ran out."""
        faults = TickFaults()
        desired = self._apply_intents()
        # Observe is not filtered by hold or drive. Slices 125 and 128 read
        # ``desired.drives_anything()`` to scope their Observe work.
        observed = self._observer.observe(
            self._run_entries(), budget, faults, self._context
        )
        # [reconciliation reads - slice 123: the plan stage, after the probes]
        links = [link.cf_project_id for link in self._store.cf_links(self._project_id)]
        probed = observed.result
        if probed is TickResult.COMPLETE:
            probed = self._probes.check(links, budget, faults, self._project_id)
        if probed is TickResult.COMPLETE:
            probed = self._plan_reads(links, budget, faults)
        shape_error = self._record_finished(observed.runs)
        watch_pointers(
            self._store,
            self._project_id,
            [o.run.entry for o in observed.runs if o.finished is None],
            faults,
        )
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
        # [route - slice 126]
        decided = self._decide(observed.runs, self._probes.results(links), desired)
        if self._act(decided, budget) is TickResult.CUT_OFF:
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

    def _record_finished(self, runs: Sequence[ObservedRun]) -> str | None:
        """Record each finished run. Returns a usage-error message, if one."""
        shape_error: str | None = None
        for observed in runs:
            if observed.finished is None:
                continue
            entry = observed.run.entry
            self._context.set(entry.node_id)
            finish.record(self._store, entry, observed.finished, self._version_label)
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
        return shape_error

    def _decide(
        self,
        runs: Sequence[ObservedRun],
        link_probes: Mapping[str, bool],
        desired: DesiredStateIndex,
    ) -> list[Action]:
        self._context.clear()
        tree = LifecycleTree(self._store.nodes_for_project(self._project_id))
        current = current_steps(tree, desired)
        dispatch = self._dispatch_view(tree, current)
        view = ProjectView(
            project_id=self._project_id,
            now=self._now(),
            tree=tree,
            # Unresolved sq_run entries the tick did not finish: what ``ready_unbusy``
            # excludes (finished ones were resolved by ``finish.record`` above).
            in_flight=tuple(o.run for o in runs if o.finished is None),
            link_probes=link_probes,
            desired=desired,
            current_steps=current,
            dispatch=dispatch.facts,
            held_checkouts=dispatch.held,
        )
        return list(decide(view, self._planners))

    def _dispatch_view(
        self, tree: LifecycleTree, current: Sequence[Node]
    ) -> DispatchView:
        """The dispatch facts, only when a dispatch planner is registered (D1).

        Without one nothing launches, so a step with no checkout is not a fault, and
        no step is blocked for it.
        """
        if not self._dispatching:
            return DispatchView({}, frozenset(), ())
        dispatch = build_dispatch_view(
            self._store,
            self._project_id,
            tree,
            current,
            self._pointer_confirmed,
            is_dir=Path.is_dir,
        )
        self.wrote = block_unresolved(self._store, dispatch.unresolved) or self.wrote
        return dispatch

    def _act(self, actions: Sequence[Action], budget: TickBudget) -> TickResult:
        for action in actions:
            self._context.set(action.node_id)
            match action:
                case BlockHumanStep():
                    # Store-only actions are applied in one transaction and not
                    # journaled: there is no external side effect to recover (D9).
                    block_human_step(self._store, action)
                    self.wrote = True
                case LaunchRun(reissue_of=str()):
                    if not budget.allows_call():
                        return TickResult.CUT_OFF
                    self._reissue(action)
                case LaunchRun():
                    if not budget.allows_call():
                        return TickResult.CUT_OFF
                    self._launch(action)
                case WriteSlicePointer():
                    if not budget.allows_call():
                        return TickResult.CUT_OFF
                    self._pointers.write(self._store, action, budget)
                    self.wrote = True
        self._context.clear()
        return TickResult.COMPLETE

    def _launch(self, action: LaunchRun) -> None:
        """Journal the command, then launch. A failed launch is recorded."""
        run_id = mint_run_id(self._now())
        build_argv(
            action.pipeline, run_id, action.params
        )  # ValueError before journaling
        entry = self._store.journal_issue(
            action.node_id,
            kind=CommandKind.SQ_RUN,
            parameters={
                PARAM_PIPELINE: action.pipeline,
                PARAM_PARAMS: dict(action.params),
                PARAM_RUN_ID: run_id,
                PARAM_CHECKOUT: str(action.checkout),
            },
        )
        self.wrote = True
        self._start(entry)

    def _reissue(self, action: LaunchRun) -> None:
        """Repeat a launch recovery found never started, under its own id (D9)."""
        decision = begin_reissue(
            self._store, action, self._supervisor_dir, self._observer.poll_run
        )
        self.wrote = True
        if isinstance(decision, ReissueLaunch):
            self._start(decision.entry)

    def _start(self, entry: JournalEntry) -> None:
        """Launch a journaled entry. A launch that cannot start is recorded."""
        started = launch(entry, self._supervisor_dir, self._popen)
        if isinstance(started, LaunchError):
            failed = LaunchFailed(started.failure, None, started.detail)
            finish.record(self._store, entry, failed, self._version_label)
            return
        self._tracker.track(entry.id, started)

    def _close_recovered(self, faults: TickFaults) -> None:
        """Close each open project escalation whose kind did not recur."""
        recurring = {kind.value for kind in faults.kinds()}
        for message in self._store.open_project_escalations(self._project_id):
            if message.fault_kind not in recurring:
                self._store.close_project_escalation(message.id, closed_by=CLOSED_BY)
                self.wrote = True
