"""A tick-level rig for dispatch: the real tick, a stub ``cf``, a fake launch.

The tick, the planners and the store are the production ones. The pointer stage runs
the stub ``cf`` binary in the step's checkout; launches go to a fake ``Popen`` that
records the command and working directory and starts nothing. Clocks do not sleep.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from amoeba.process import RunOutcome, RunOutcomeDocument
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.launch import log_paths
from amoeba.runner.project_config import ProjectSettings
from amoeba.store import (
    PARAM_RUN_ID,
    CommandKind,
    JournalEntry,
    Node,
    NodeStatus,
    Store,
)
from runner.dispatch.pointer_support import CfWorld
from runner.gate_rig import rig_checkout
from runner.observe_support import Child
from runner.tick_support import (
    PROJECT,
    Popen,
    Rig,
    drive_project,
    ready_slice,
)

CF_PROJECT = "cf-a"
#: The pipeline the rig's project is configured with.
PIPELINE = "p456"
#: The slice index the stub CF names, and its name (a review file carries it).
CF_SLICE_INDEX = 125
CF_SLICE_NAME = "run-dispatch-and-outcome-ingestion"


class RecordingPopen(Popen):
    """The tick rig's fake ``Popen``, remembering what it was asked to start."""

    def __init__(self, store: Store) -> None:
        super().__init__(store)
        self.argvs: list[list[str]] = []
        self.cwds: list[str] = []
        #: A test sets this to answer a launch itself; it returns ``None`` to decline.
        self.delegate: Callable[..., Child | None] | None = None

    def __call__(self, argv: list[str], **kwargs: Any) -> Child:
        self.argvs.append(argv)
        self.cwds.append(str(kwargs.get("cwd")))
        if self.delegate is not None and (child := self.delegate(argv, **kwargs)):
            return child
        return super().__call__(argv, **kwargs)


class DispatchRig:
    """One project, driven, with the dispatch planner and the stub ``cf``."""

    def __init__(
        self, tmp_path: Path, store: Store, *, with_snapshot: bool = True
    ) -> None:
        self.store = store
        self.world = CfWorld(tmp_path / "world")
        self.tick_rig = Rig(tmp_path / "tick", store)
        self.popen = RecordingPopen(store)
        self.tick_rig.popen = self.popen
        self.tick_rig.planners = (DispatchPlanner(),)
        self.tick_rig.project_settings = ProjectSettings(pipeline=PIPELINE)
        self.use_clean_checkouts()
        drive_project(store, PROJECT)
        if with_snapshot:
            self.snapshot()

    def use_clean_checkouts(self) -> None:
        """Make each checkout a clean git repository, with a stub ``cf`` for config.

        The pre-dispatch check reads the checkout's git state and the target branch;
        tests of a blocked launch change the repository or the knobs.
        """
        rig_checkout(self.world.root)
        rig_checkout(self.world.second)
        self.tick_rig.gate_run = self.world.run({})

    def snapshot(
        self,
        worktrees: dict[str, dict[str, object]] | None = None,
        project_path: str | None = None,
        observed_at: datetime | None = None,
    ) -> None:
        """Record the observed CF snapshot dispatch resolves checkouts from."""
        self.store.record_cf_snapshot(
            self.world.snapshot_input(
                PROJECT, CF_PROJECT, worktrees, project_path, observed_at
            )
        )

    def step(self, name: str, slice_index: int) -> Node:
        """A ready slice, the unit of work (named ``step`` for the tests' sake)."""
        return self.slice_and_step(name, slice_index)[1]

    def slice_and_step(self, name: str, slice_index: int) -> tuple[Node, Node]:
        """``(slice node, the same node)``: the slice is the unit of work (132, D1)."""
        node = ready_slice(
            self.store, PROJECT, name, CF_PROJECT, slice_index=slice_index
        )
        if slice_index == CF_SLICE_INDEX:
            # CF knows this index by its own name; reviews are attributed by it.
            reference = replace(node.cf, slice_name=CF_SLICE_NAME)
            node = self.store.update_cf_reference(node.id, reference)
        return node, node

    def tick(self) -> None:
        self.tick_rig.tick()

    def run_of(self, node: Node) -> JournalEntry:
        """The one unresolved ``sq_run`` entry of ``node``."""
        [entry] = [
            e for e in self.entries(CommandKind.SQ_RUN, node) if not e.is_resolved
        ]
        return entry

    def end_run(
        self, node: Node, outcome: RunOutcome = RunOutcome.COMPLETED, **fields: object
    ) -> None:
        """Confirm ``node``'s run, make it end as ``outcome``, and tick once.

        ``fields`` are extra outcome-document fields (``reviews``, ``checkpoint``,
        ``failure``). The launch is confirmed directly, so this is one tick: the
        one that polls the run, records it, and then decides.
        """
        entry = self.run_of(node)
        run_id = str(entry.parameters[PARAM_RUN_ID])
        self.tick_rig.tracker.confirm(entry.id)
        log_paths(self.tick_rig.supervisor_dir, entry.id).stderr.write_text(
            f"run_id={run_id}\n"
        )
        self.tick_rig.poll.answers.append(
            RunOutcomeDocument.model_validate(
                {
                    "run_id": run_id,
                    "outcome": outcome.value,
                    "status": outcome.value,
                    **fields,
                }
            )
        )
        self.tick_rig.clock.seconds += 20.0
        self.tick()

    def entries(self, kind: CommandKind, node: Node) -> list[JournalEntry]:
        found = self.store.journal_entries(PROJECT, node_id=node.id)
        return [entry for entry in found if entry.kind is kind]

    def status(self, node: Node) -> NodeStatus:
        found = self.store.get_node(node.id)
        assert found is not None
        return found.status
