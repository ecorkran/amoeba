"""A tick-level rig for dispatch: the real tick, a stub ``cf``, a fake launch.

The tick, the planners and the store are the production ones. The pointer stage runs
the stub ``cf`` binary in the step's checkout; launches go to a fake ``Popen`` that
records the command and working directory and starts nothing. Clocks do not sleep.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cf_harness import observed

from amoeba.runner.dispatch.observe_pointer import PointerStage
from amoeba.runner.dispatch.planner import DispatchPlanner
from amoeba.runner.lifecycle.steps import (
    STEP_MAP,
    STEP_SEQUENCE,
    LifecycleStep,
    StepLevel,
)
from amoeba.store import CommandKind, JournalEntry, Node, NodeStatus, Store
from amoeba.upstream.context_forge import (
    FIELD_PROJECT_PATH,
    STATE_PROJECT_KEY,
    STATE_WORKTREES_KEY,
)
from runner.dispatch.pointer_support import CfWorld
from runner.observe_support import Child
from runner.tick_support import (
    GRACE,
    PROJECT,
    Popen,
    Rig,
    drive_project,
    ready_slice_step,
)

CF_PROJECT = "cf-a"


class RecordingPopen(Popen):
    """The tick rig's fake ``Popen``, remembering what it was asked to start."""

    def __init__(self, store: Store) -> None:
        super().__init__(store)
        self.argvs: list[list[str]] = []
        self.cwds: list[str] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> Child:
        self.argvs.append(argv)
        self.cwds.append(str(kwargs.get("cwd")))
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
        self.use_world()
        drive_project(store, PROJECT)
        if with_snapshot:
            self.snapshot()

    def use_world(self, knobs: dict[str, str] | None = None) -> None:
        """Run the pointer stage against the stub ``cf`` (with ``knobs``)."""
        self.tick_rig.pointers = PointerStage(
            self.world.run(knobs), 8.0, GRACE, self.tick_rig.clock.wall
        )

    def snapshot(
        self,
        worktrees: dict[str, dict[str, object]] | None = None,
        project_path: str | None = None,
    ) -> None:
        """Record the observed CF snapshot dispatch resolves checkouts from."""
        world = self.world
        default = {
            "wt_a": world.worktree_entry("wt_a", world.root, 100, 199),
            "wt_b": world.worktree_entry("wt_b", world.second, 200, 299),
        }
        state = {
            STATE_PROJECT_KEY: {FIELD_PROJECT_PATH: project_path or str(world.root)},
            STATE_WORKTREES_KEY: default if worktrees is None else worktrees,
        }
        self.store.record_cf_snapshot(
            observed(PROJECT, CF_PROJECT, state=state, changed=[])
        )

    def step(
        self,
        name: str,
        slice_index: int,
        step: LifecycleStep = LifecycleStep.SLICE_DESIGN,
    ) -> Node:
        """A ready slice-level step under a new slice of that index."""
        return self.slice_and_step(name, slice_index, step)[1]

    def slice_and_step(
        self,
        name: str,
        slice_index: int,
        step: LifecycleStep = LifecycleStep.SLICE_DESIGN,
    ) -> tuple[Node, Node]:
        """``(slice node, ready step node)``; earlier steps of the slice are done."""
        earlier = tuple(
            s
            for s in STEP_SEQUENCE[: STEP_SEQUENCE.index(step)]
            if STEP_MAP[s].level is StepLevel.SLICE
        )
        return ready_slice_step(
            self.store, name, PROJECT, step, CF_PROJECT, slice_index, done_steps=earlier
        )

    def tick(self) -> None:
        self.tick_rig.tick()

    def entries(self, kind: CommandKind, node: Node) -> list[JournalEntry]:
        found = self.store.journal_entries(PROJECT, node_id=node.id)
        return [entry for entry in found if entry.kind is kind]

    def status(self, node: Node) -> NodeStatus:
        found = self.store.get_node(node.id)
        assert found is not None
        return found.status
