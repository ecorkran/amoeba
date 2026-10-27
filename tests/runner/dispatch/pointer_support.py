"""A stub ``cf`` rig for the pointer tests: state file, worktrees, step and budgets."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from datetime import datetime
from functools import partial
from itertools import count
from pathlib import Path
from typing import Any, cast

from cf_harness import observed
from cf_stub import STATE_ENV, write_cf_state, write_cf_stub

from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfRun
from amoeba.runner.decide import WriteSlicePointer
from amoeba.runner.dispatch.checkout import Checkout
from amoeba.store import CFReference, CFSnapshotInput, NodeKind, Store
from amoeba.upstream.context_forge import (
    FIELD_PROJECT_PATH,
    STATE_PROJECT_KEY,
    STATE_WORKTREES_KEY,
)

PROJECT = "demo"
CF_ID = "project_1_abc"
STEM = "125-slice.run-dispatch-and-outcome-ingestion"
TIMEOUT = 30.0


class Host:
    """A host that has not been asked to stop."""

    stop_requested = False


def generous_budget() -> TickBudget:
    return TickBudget(1_000_000.0, Host(), lambda: 0.0)


def budget_allowing(calls: int) -> TickBudget:
    """A budget whose clock moves one step per check: ``calls`` checks pass."""
    return TickBudget(calls - 0.5, Host(), partial(next, count()))


class CfWorld:
    """Two worktrees (indexes 100-199 and 200-299), a stub ``cf`` over their state."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "main"
        self.second = tmp_path / "second"
        self.root.mkdir(parents=True)
        self.second.mkdir(parents=True)
        self.state_path = tmp_path / "cf-state.json"
        self.bin_dir = write_cf_stub(tmp_path / "bin")
        write_cf_state(
            self.state_path,
            cf_project_id=CF_ID,
            project_path=self.root,
            worktrees=[
                self.worktree_entry("wt_a", self.root, 100, 199),
                self.worktree_entry("wt_b", self.second, 200, 299),
            ],
            slices={
                125: STEM,
                126: "126-slice.next-in-root",
                225: "225-slice.second",
            },
        )

    def snapshot_input(
        self,
        project_id: str,
        cf_project_id: str,
        worktrees: dict[str, dict[str, object]] | None = None,
        project_path: str | None = None,
        observed_at: datetime | None = None,
    ) -> CFSnapshotInput:
        """An observed snapshot of this world: what dispatch resolves checkouts from."""
        default = {
            "wt_a": self.worktree_entry("wt_a", self.root, 100, 199),
            "wt_b": self.worktree_entry("wt_b", self.second, 200, 299),
        }
        state = {
            STATE_PROJECT_KEY: {FIELD_PROJECT_PATH: project_path or str(self.root)},
            STATE_WORKTREES_KEY: default if worktrees is None else worktrees,
        }
        when = {} if observed_at is None else {"observed_at": observed_at}
        return observed(project_id, cf_project_id, state=state, changed=[], **when)

    @staticmethod
    def worktree_entry(
        worktree_id: str, path: Path, low: int, high: int
    ) -> dict[str, object]:
        return {
            "id": worktree_id,
            "name": worktree_id,
            "worktreePath": str(path),
            "indexRange": [low, high],
        }

    def run(self, knobs: Mapping[str, str] | None = None) -> CfRun:
        env = {
            **os.environ,
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}",
            STATE_ENV: str(self.state_path),
            **(knobs or {}),
        }

        def call(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            # A caller's own env (git runs with prompts off) is kept; the world's
            # stub PATH and knobs win.
            merged = {**kwargs.pop("env", {}), **env}
            return cast(
                "subprocess.CompletedProcess[str]",
                subprocess.run(argv, env=merged, **kwargs),  # pyright: ignore[reportUnknownMemberType]
            )

        return call


class Rig(CfWorld):
    """The world, plus a step under a slice node, for the pointer-write tests."""

    def __init__(self, tmp_path: Path, store: Store) -> None:
        super().__init__(tmp_path)
        self.store = store
        self.slice_node = store.create_node(
            project_id=PROJECT,
            kind=NodeKind.SLICE,
            title="slice",
            cf=CFReference(project="cf-a", index=125),
        )
        self.node = store.create_node(
            project_id=PROJECT,
            kind=NodeKind.PHASE_OR_ARTIFACT,
            title="tasks",
            parent_id=self.slice_node.id,
        )

    def action(self, index: int = 125, where: str = "root") -> WriteSlicePointer:
        path = self.root if where == "root" else self.second
        worktree = "wt_a" if where == "root" else "wt_b"
        return WriteSlicePointer(self.node.id, CF_ID, index, Checkout(path, worktree))
