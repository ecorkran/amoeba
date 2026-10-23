"""The tick rig shared by the tick and probe tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from feed_harness import apply

from amoeba.runner.budget import TickBudget, TickResult
from amoeba.runner.decide import Action, LaunchRun, ProjectView
from amoeba.runner.faults import NodeContext
from amoeba.runner.launch import (
    LAUNCH_LOGS_DIRNAME,
    LaunchTracker,
)
from amoeba.runner.observe import RunObserver
from amoeba.runner.probes import LinkProbes
from amoeba.runner.tick import ProjectTick
from amoeba.store import Store, SubmissionKind
from amoeba.store.inbox_models import LINK_CF_PROJECT_ID
from runner.observe_support import (
    GRACE,
    Child,
    Clock,
    FakeCf,
    Host,
    ScriptedPoll,
)

PROJECT = "demo"


class Planner:
    """Launches ``noop`` for each runnable node it is shown, and records views."""

    def __init__(self, checkout: Path) -> None:
        self.checkout = checkout
        self.views: list[ProjectView] = []

    def plan(self, view: ProjectView) -> Sequence[Action]:
        self.views.append(view)
        return [
            LaunchRun(n.id, "noop", {"k": "v"}, self.checkout)
            for n in view.runnable_nodes
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
        self.planner = Planner(tmp_path)
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
            planners=(self.planner,),
            observer=self.observer,
            probes=self.probes,
            tracker=self.tracker,
            popen=self.popen,
            now=self.clock.wall,
            context=self.context,
        )
        budget = TickBudget(self.deadline, Host(), self.clock.monotonic)
        return tick.run(budget), tick


def link(store: Store, submission_id: str, cf_id: str, project: str) -> None:
    """Apply a link-CF-project submission, linking ``project`` to ``cf_id``."""
    apply(
        store,
        submission_id,
        SubmissionKind.LINK_CF_PROJECT,
        {LINK_CF_PROJECT_ID: cf_id},
        project,
    )
