"""The tick rig shared by the tick and probe tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from itertools import count
from pathlib import Path
from typing import Any

from feed_harness import apply

from amoeba.process import ProcessSettings
from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.decide import Action, InFlightRun, LaunchRun, ProjectView
from amoeba.runner.dispatch.observe_pointer import PointerStage
from amoeba.runner.faults import NodeContext
from amoeba.runner.intent.apply import apply_pending_intents
from amoeba.runner.intent.governance import DesiredStateIndex, current_steps
from amoeba.runner.launch import (
    LAUNCH_LOGS_DIRNAME,
    LaunchTracker,
)
from amoeba.runner.lifecycle.cadence import PlanReadSchedule
from amoeba.runner.lifecycle.plan_stage import PlanStage
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.observe import RunObserver
from amoeba.runner.probes import LinkProbes
from amoeba.runner.tenant import RunnerTenant
from amoeba.runner.tick import ProjectTick
from amoeba.store import (
    CFReference,
    DesiredState,
    Node,
    NodeKind,
    NodeStatus,
    Store,
    SubmissionKind,
)
from amoeba.store.inbox_models import LINK_CF_PROJECT_ID
from runner.intent.intent_support import submit
from runner.observe_support import (
    GRACE,
    Child,
    Clock,
    FakeCf,
    Host,
    ScriptedPoll,
)

PROJECT = "demo"
PLAN_READ_INTERVAL = 30.0
VIEW_NOW = datetime(2026, 10, 23, tzinfo=UTC)


def view_for(
    tree: LifecycleTree,
    rows: Sequence[DesiredState] = (),
    in_flight: tuple[InFlightRun, ...] = (),
) -> ProjectView:
    """A view over ``tree`` and hand-built desired-state rows, with current steps."""
    index = DesiredStateIndex(rows)
    return ProjectView(
        project_id=PROJECT,
        now=VIEW_NOW,
        tree=tree,
        in_flight=in_flight,
        link_probes={},
        desired=index,
        current_steps=current_steps(tree, index),
    )


_INITIATIVE_INDEXES = count(100)


def ready_step(store: Store, project_id: str = PROJECT) -> Node:
    """A ready lifecycle step: the architecture step of a new linked initiative.

    Launch-path tests need a node a planner may act on, and only a ready step
    can be a current step. Each call makes a new initiative.
    """
    initiative = store.create_node(
        project_id=project_id,
        kind=NodeKind.INITIATIVE,
        title="initiative",
        cf=CFReference(project="cf-a", index=next(_INITIATIVE_INDEXES)),
    )
    return store.create_node(
        project_id=project_id,
        kind=NodeKind.PHASE_OR_ARTIFACT,
        title="architecture",
        parent_id=initiative.id,
        cf=CFReference(project="cf-a", phase=LifecycleStep.ARCHITECTURE.value),
    )


_SLICE_INDEXES = count(200)


def ready_slice_step(
    store: Store,
    slice_name: str,
    project_id: str = PROJECT,
    step: LifecycleStep = LifecycleStep.SLICE_DESIGN,
    cf_project: str = "cf-a",
    slice_index: int | None = None,
    done_steps: Sequence[LifecycleStep] = (),
) -> tuple[Node, Node]:
    """A ready slice-level step under a linked slice: ``(slice node, step node)``.

    Its initiative has the architecture and slice-plan steps done, which is what a
    slice design waits for. Each call makes a new initiative and slice.
    """
    initiative = store.create_node(
        project_id=project_id,
        kind=NodeKind.INITIATIVE,
        title="initiative",
        cf=CFReference(project=cf_project, index=next(_INITIATIVE_INDEXES)),
    )
    for done in (LifecycleStep.ARCHITECTURE, LifecycleStep.SLICE_PLAN):
        store.create_node(
            project_id=project_id,
            kind=NodeKind.PHASE_OR_ARTIFACT,
            title=done.value,
            parent_id=initiative.id,
            status=NodeStatus.DONE,
            cf=CFReference(project=cf_project, phase=done.value),
        )
    slice_node = store.create_node(
        project_id=project_id,
        kind=NodeKind.SLICE,
        title=slice_name,
        parent_id=initiative.id,
        cf=CFReference(
            project=cf_project,
            slice_name=slice_name,
            index=next(_SLICE_INDEXES) if slice_index is None else slice_index,
        ),
    )
    for done in done_steps:
        store.create_node(
            project_id=project_id,
            kind=NodeKind.PHASE_OR_ARTIFACT,
            title=done.value,
            parent_id=slice_node.id,
            status=NodeStatus.DONE,
            cf=CFReference(project=cf_project, phase=done.value),
        )
    step_node = store.create_node(
        project_id=project_id,
        kind=NodeKind.PHASE_OR_ARTIFACT,
        title=step.value,
        parent_id=slice_node.id,
        cf=CFReference(project=cf_project, phase=step.value),
    )
    return slice_node, step_node


def drive_project(store: Store, project_id: str = PROJECT) -> None:
    """Drive the whole project now: submit a drive intent and apply it directly.

    Does not rely on the tick's apply stage, so tests can use it before that exists.
    """
    submit(store, {"intent": "drive"}, project_id=project_id)
    apply_pending_intents(store, project_id)


def runnable_unbusy(view: ProjectView) -> list[Node]:
    """Current steps with no run in flight: what a launch-path test planner acts on."""
    busy = {run.entry.node_id for run in view.in_flight}
    return [node for node in view.current_steps if node.id not in busy]


class Planner:
    """Launches ``noop`` for each runnable node it is shown, and records views."""

    def __init__(self, checkout: Path) -> None:
        self.checkout = checkout
        self.views: list[ProjectView] = []

    def plan(self, view: ProjectView) -> Sequence[Action]:
        self.views.append(view)
        return [
            LaunchRun(n.id, "noop", {"k": "v"}, self.checkout)
            for n in runnable_unbusy(view)
        ]


class Popen:
    def __init__(self, store: Store, error: OSError | None = None) -> None:
        self.store = store
        self.error = error
        self.calls = 0
        self.open_entries_at_call: list[int] = []
        self.on_call: Any = None

    def __call__(self, argv: list[str], **kwargs: Any) -> Child:
        self.calls += 1
        if self.on_call is not None:
            self.on_call()
        self.open_entries_at_call.append(
            len(self.store.unresolved_journal_entries(PROJECT))
        )
        if self.error is not None:
            raise self.error
        return Child(None)


class Rig:
    def __init__(self, tmp_path: Path, store: Store, *answers: Any) -> None:
        self.store = store
        self.supervisor_dir = tmp_path / "supervisor"
        (self.supervisor_dir / LAUNCH_LOGS_DIRNAME).mkdir(parents=True)
        self.clock = Clock()
        self.poll = ScriptedPoll(*answers)
        self.tracker = LaunchTracker()
        self.cf = FakeCf()
        self.probes = LinkProbes(run=self.cf, timeout_seconds=8.0)
        self.plans = PlanStage(
            schedule=PlanReadSchedule(PLAN_READ_INTERVAL, self.clock.monotonic),
            run=self.cf,
            timeout_seconds=8.0,
        )
        self.pointers = PointerStage(self.cf, 8.0, GRACE, self.clock.wall)
        self.planner = Planner(tmp_path)
        self.planners: tuple[Any, ...] = (self.planner,)
        self.popen = Popen(store)
        self.context = NodeContext()
        self.deadline = 1_000_000.0
        self.observer = RunObserver(
            supervisor_dir=self.supervisor_dir,
            tracker=self.tracker,
            poll=self.poll,
            now=self.clock.wall,
            monotonic=self.clock.monotonic,
            launch_grace_seconds=GRACE,
            run_poll_interval_seconds=15.0,
        )

    def tick(self) -> tuple[TickResult, ProjectTick]:
        tick = ProjectTick(
            project_id=PROJECT,
            store=self.store,
            supervisor_dir=self.supervisor_dir,
            planners=self.planners,
            observer=self.observer,
            probes=self.probes,
            plans=self.plans,
            pointers=self.pointers,
            tracker=self.tracker,
            popen=self.popen,
            now=self.clock.wall,
            context=self.context,
            version_label=TEST_VERSION_LABEL,
        )
        budget = TickBudget(self.deadline, Host(), self.clock.monotonic)
        return tick.run(budget), tick


#: The ``sq --version`` label the rig's ingestion is given; not a real version.
TEST_VERSION_LABEL = "sq-test-label"

TENANT_SETTINGS = ProcessSettings(
    tick_deadline_seconds=5.0, run_poll_interval_seconds=15.0
)


class StoreHost:
    """A tenant host over one project's store."""

    stop_requested = False
    project_ids = (PROJECT,)

    def __init__(self, store: Store) -> None:
        self._store = store

    def store_for(self, project_id: str) -> Store:
        return self._store


def tenant_for(rig: Rig) -> RunnerTenant:
    """A tenant built from the rig's parts, so its fault boundary is in play."""
    return RunnerTenant(
        settings=TENANT_SETTINGS,
        supervisor_dir=rig.supervisor_dir,
        planners=rig.planners,
        popen=rig.popen,
        cf_run=rig.cf,
        poll=rig.poll,
        now=rig.clock.wall,
        monotonic=rig.clock.monotonic,
        version_label=TEST_VERSION_LABEL,
    )


def link(store: Store, submission_id: str, cf_id: str, project: str) -> None:
    """Apply a link-CF-project submission, linking ``project`` to ``cf_id``."""
    apply(
        store,
        submission_id,
        SubmissionKind.LINK_CF_PROJECT,
        {LINK_CF_PROJECT_ID: cf_id},
        project,
    )
