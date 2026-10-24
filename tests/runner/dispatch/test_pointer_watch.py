"""D11: a pointer someone else moved away from a run in flight."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from cf_harness import OBSERVED_AT, observed

from amoeba.runner.dispatch.pointer_watch import (
    MovedPointer,
    WatchedRun,
    pointer_moved,
)
from amoeba.store import CFSnapshot, Store
from amoeba.upstream.context_forge import (
    FIELD_INDEX_RANGE,
    FIELD_PROJECT_PATH,
    FIELD_WORKTREE_PATH,
    STATE_PROJECT_KEY,
    STATE_WORKTREES_KEY,
)

PROJECT = "demo"
CF_ID = "cf-a"
WRITE_RESOLVED = OBSERVED_AT
LATER = OBSERVED_AT + timedelta(seconds=30)
EARLIER = OBSERVED_AT - timedelta(seconds=30)
STEM_125 = "125-slice.mine"
STEM_130 = "130-slice.someone-else"


def _snapshot(
    store: Store,
    *,
    active: object = STEM_125,
    observed_at: datetime = LATER,
    worktree: bool = True,
) -> CFSnapshot:
    worktrees: dict[str, dict[str, object]] = {}
    project: dict[str, object] = {FIELD_PROJECT_PATH: "/work/a"}
    if worktree:
        worktrees["wt_a"] = {
            FIELD_WORKTREE_PATH: "/work/a",
            FIELD_INDEX_RANGE: [100, 199],
            "activeSlice": active,
        }
    else:
        project["fileSlice"] = active
    state = {STATE_PROJECT_KEY: project, STATE_WORKTREES_KEY: worktrees}
    return store.record_cf_snapshot(
        observed(PROJECT, CF_ID, state=state, changed=[], observed_at=observed_at)
    )


def _run(worktree_id: str | None = "wt_a", index: int = 125) -> WatchedRun:
    return WatchedRun(
        node_id="node-1",
        run_id="run-1",
        cf_project_id=CF_ID,
        worktree_id=worktree_id,
        slice_index=index,
        pointer_resolved_at=WRITE_RESOLVED,
    )


def test_the_same_index_is_no_move(store: Store) -> None:
    snapshots = {CF_ID: _snapshot(store, active=STEM_125)}

    assert pointer_moved([_run()], snapshots) == []


def test_a_different_index_is_a_move(store: Store) -> None:
    snapshots = {CF_ID: _snapshot(store, active=STEM_130)}

    assert pointer_moved([_run()], snapshots) == [
        MovedPointer("node-1", "run-1", "wt_a", STEM_130)
    ]


def test_a_snapshot_observed_before_the_write_resolved_is_ignored(
    store: Store,
) -> None:
    snapshots = {CF_ID: _snapshot(store, active=STEM_130, observed_at=EARLIER)}

    assert pointer_moved([_run()], snapshots) == []


def test_a_snapshot_observed_at_the_moment_the_write_resolved_is_ignored(
    store: Store,
) -> None:
    snapshots = {CF_ID: _snapshot(store, active=STEM_130, observed_at=WRITE_RESOLVED)}

    assert pointer_moved([_run()], snapshots) == []


def test_no_snapshot_is_no_move() -> None:
    assert pointer_moved([_run()], {}) == []
    assert pointer_moved([_run()], {CF_ID: None}) == []


def test_a_project_without_worktrees_reads_file_slice(store: Store) -> None:
    snapshots = {CF_ID: _snapshot(store, active=STEM_130, worktree=False)}

    assert pointer_moved([_run(worktree_id=None)], snapshots) == [
        MovedPointer("node-1", "run-1", None, STEM_130)
    ]
    same = {CF_ID: _snapshot(store, active=STEM_125, worktree=False)}
    assert pointer_moved([_run(worktree_id=None)], same) == []


@pytest.mark.parametrize("value", ["not a slice stem", "", None, 125])
def test_a_value_that_does_not_parse_is_not_a_move(store: Store, value: object) -> None:
    snapshots = {CF_ID: _snapshot(store, active=value)}

    assert pointer_moved([_run()], snapshots) == []


def test_a_worktree_the_snapshot_does_not_carry_is_not_a_move(store: Store) -> None:
    snapshots = {CF_ID: _snapshot(store, active=STEM_130)}

    assert pointer_moved([_run(worktree_id="wt_other")], snapshots) == []


def test_every_moved_run_is_listed_and_the_still_pointed_are_not(
    store: Store,
) -> None:
    snapshots = {CF_ID: _snapshot(store, active=STEM_130)}
    moved = _run(index=125)
    still = WatchedRun("node-2", "run-2", CF_ID, "wt_a", 130, WRITE_RESOLVED)

    found = pointer_moved([moved, still], snapshots)

    assert [m.node_id for m in found] == ["node-1"]
