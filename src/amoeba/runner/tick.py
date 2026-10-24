"""One project's tick: observe, record finished runs, decide, act, close.

The sequence is fixed code (D1). Slots later slices fill are marked in comments
only: intents (124) before observe, reconciliation reads (123) in observe, the
body of ``finish.record`` (125), routing (126) after record.
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
    LaunchRun,
    Planner,
    ProjectView,
    decide,
)
from amoeba.runner.faults import (
    LaunchFailure,
    NodeContext,
    TickFaults,
    raise_expected_faults,
)
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
    Store,
)

#: Who closes a project escalation that stopped recurring.
CLOSED_BY: Final = "runner"


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
        tracker: LaunchTracker,
        popen: PopenFactory,
        now: Callable[[], datetime],
        context: NodeContext,
    ) -> None:
        self._project_id = project_id
        self._store = store
        self._supervisor_dir = supervisor_dir
        self._planners = planners
        self._observer = observer
        self._probes = probes
        self._plans = plans
        self._tracker = tracker
        self._popen = popen
        self._now = now
        self._context = context
        self.wrote = False
        """Whether this tick wrote to the store or issued a command."""

    def run(self, budget: TickBudget) -> TickResult:
        """Run the stages in order; ``CUT_OFF`` when the budget ran out."""
        faults = TickFaults()
        # [apply intents - slice 124]
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
        self.wrote = (
            raise_expected_faults(self._store, self._project_id, faults) or self.wrote
        )
        if shape_error is not None:
            raise UpstreamShapeError(shape_error)
        if probed is TickResult.CUT_OFF:
            return TickResult.CUT_OFF
        # [route - slice 126]
        decided = self._decide(observed.runs, self._probes.results(links))
        if self._act(decided, budget) is TickResult.CUT_OFF:
            return TickResult.CUT_OFF
        self._close_recovered(faults)
        return TickResult.COMPLETE

    def _plan_reads(
        self, links: Sequence[str], budget: TickBudget, faults: TickFaults
    ) -> TickResult:
        """Read and reconcile each due link whose probe passed (D7)."""
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
            finish.record(self._store, entry, observed.finished)
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
        self, runs: Sequence[ObservedRun], link_probes: Mapping[str, bool]
    ) -> list[LaunchRun]:
        self._context.clear()
        view = ProjectView(
            project_id=self._project_id,
            now=self._now(),
            tree=LifecycleTree(self._store.nodes_for_project(self._project_id)),
            in_flight=tuple(o.run for o in runs if o.finished is None),
            link_probes=link_probes,
        )
        return list(decide(view, self._planners))

    def _act(self, actions: Sequence[LaunchRun], budget: TickBudget) -> TickResult:
        for action in actions:
            if not budget.allows_call():
                return TickResult.CUT_OFF
            self._context.set(action.node_id)
            self._launch(action)
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
        started = launch(entry, self._supervisor_dir, self._popen)
        if isinstance(started, LaunchError):
            failed = LaunchFailed(started.failure, None, started.detail)
            finish.record(self._store, entry, failed)
            return
        self._tracker.track(entry.id, started)

    def _close_recovered(self, faults: TickFaults) -> None:
        """Close each open project escalation whose kind did not recur."""
        recurring = {kind.value for kind in faults.kinds()}
        for message in self._store.open_project_escalations(self._project_id):
            if message.fault_kind not in recurring:
                self._store.close_project_escalation(message.id, closed_by=CLOSED_BY)
                self.wrote = True
