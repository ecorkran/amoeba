"""A stub ``cf`` world for the dispatch tests: worktrees, snapshots and budgets."""

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
from cf_stub import write_cf_stub

from amoeba.runner.budget import TickBudget
from amoeba.runner.cf_call import CfRun
from amoeba.store import CFSnapshotInput
from amoeba.upstream.context_forge import (
    FIELD_PROJECT_PATH,
    STATE_PROJECT_KEY,
    STATE_WORKTREES_KEY,
)

PROJECT = "demo"


class Host:
    """A host that has not been asked to stop."""

    stop_requested = False


def generous_budget() -> TickBudget:
    return TickBudget(1_000_000.0, Host(), lambda: 0.0)


def budget_allowing(calls: int) -> TickBudget:
    """A budget whose clock moves one step per check: ``calls`` checks pass."""
    return TickBudget(calls - 0.5, Host(), partial(next, count()))


class CfWorld:
    """Two worktrees (indexes 100-199 and 200-299) and a stub ``cf`` on ``PATH``."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "main"
        self.second = tmp_path / "second"
        self.root.mkdir(parents=True)
        self.second.mkdir(parents=True)
        self.bin_dir = write_cf_stub(tmp_path / "bin")

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
