"""D11 for a continuation: only snapshots after it was issued count (slice 127)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest
from cf_harness import OBSERVED_AT, observed
from sq_run_fixtures import sq_run_parameters

from amoeba.runner.dispatch.pointer_watch import pointer_moved, watched_runs
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_CONTINUATION,
    PARAM_CONTINUES,
    PARAM_EXPECTED,
    PARAM_EXPECTED_SLICE_INDEX,
    PARAM_PROJECT,
    CFSnapshot,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    NodeKind,
    Store,
)
from amoeba.upstream.context_forge import (
    FIELD_INDEX_RANGE,
    FIELD_PROJECT_PATH,
    FIELD_WORKTREE_PATH,
    STATE_PROJECT_KEY,
    STATE_WORKTREES_KEY,
)

PROJECT = "demo"
CF_ID = "cf-a"
POINTER_RESOLVED = OBSERVED_AT
CONTINUATION_ISSUED = OBSERVED_AT + timedelta(hours=2)
DURING_PAUSE = OBSERVED_AT + timedelta(hours=1)
AFTER_RESUME = OBSERVED_AT + timedelta(hours=3)
MOVED_TO = "130-slice.someone-else"


def _stamp(store: Store, entry: JournalEntry, **columns: datetime) -> None:
    with sqlite3.connect(store.path) as connection:
        for column, value in columns.items():
            connection.execute(
                f"UPDATE command_journal SET {column} = ? WHERE id = ?",
                (value.isoformat(), entry.id),
            )


def _snapshot(store: Store, observed_at: datetime) -> CFSnapshot:
    worktree = {
        FIELD_WORKTREE_PATH: "/work/a",
        FIELD_INDEX_RANGE: [100, 199],
        "activeSlice": MOVED_TO,
    }
    state = {
        STATE_PROJECT_KEY: {FIELD_PROJECT_PATH: "/work/a"},
        STATE_WORKTREES_KEY: {"wt_a": worktree},
    }
    return store.record_cf_snapshot(
        observed(PROJECT, CF_ID, state=state, changed=[], observed_at=observed_at)
    )


@pytest.fixture
def staged(store: Store) -> tuple[JournalEntry, JournalEntry]:
    """A step with a resolved pointer write, a paused run, and a continuation."""
    node = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="s")
    pointer = store.journal_issue(
        node.id,
        kind=CommandKind.CF_WRITE,
        parameters={
            PARAM_PROJECT: CF_ID,
            PARAM_CHECKOUT: "/work/a",
            PARAM_EXPECTED: {},
            PARAM_EXPECTED_SLICE_INDEX: 125,
        },
    )
    store.journal_resolve(
        pointer.id, outcome=JournalOutcome.COMPLETED, result={"worktree_id": "wt_a"}
    )
    _stamp(store, pointer, issued_at=POINTER_RESOLVED, resolved_at=POINTER_RESOLVED)
    base: dict[str, object] = {
        "pipeline": "P4",
        "params": {},
        PARAM_CHECKOUT: "/work/a",
    }
    plain = store.journal_issue(
        node.id,
        kind=CommandKind.SQ_RUN,
        parameters=sq_run_parameters(base, run_id="run-1"),
    )
    _stamp(store, plain, issued_at=POINTER_RESOLVED + timedelta(minutes=1))
    parameters = sq_run_parameters(base, run_id="run-1") | {
        PARAM_CONTINUATION: "retry",
        PARAM_CONTINUES: plain.id,
    }
    continuation = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=parameters
    )
    _stamp(store, continuation, issued_at=CONTINUATION_ISSUED)
    reread = store.journal_entry(continuation.id)
    assert reread is not None
    return plain, reread


def test_a_plain_run_is_watched_from_the_pointer_write(
    store: Store, staged: tuple[JournalEntry, JournalEntry]
) -> None:
    plain, _ = staged
    reread = store.journal_entry(plain.id)
    assert reread is not None

    [run] = watched_runs(store, PROJECT, [reread])

    assert run.pointer_resolved_at == POINTER_RESOLVED


def test_a_continuation_is_watched_from_its_own_issue(
    store: Store, staged: tuple[JournalEntry, JournalEntry]
) -> None:
    _, continuation = staged

    [run] = watched_runs(store, PROJECT, [continuation])

    assert run.slice_index == 125 and run.worktree_id == "wt_a"
    assert run.pointer_resolved_at == CONTINUATION_ISSUED


def test_a_pointer_moved_after_the_continuation_was_issued_is_reported(
    store: Store, staged: tuple[JournalEntry, JournalEntry]
) -> None:
    _, continuation = staged
    snapshots = {CF_ID: _snapshot(store, AFTER_RESUME)}

    moved = pointer_moved(watched_runs(store, PROJECT, [continuation]), snapshots)

    assert [m.observed for m in moved] == [MOVED_TO]


def test_a_move_during_the_pause_is_not_reported(
    store: Store, staged: tuple[JournalEntry, JournalEntry]
) -> None:
    plain, continuation = staged
    reread = store.journal_entry(plain.id)
    assert reread is not None
    snapshots = {CF_ID: _snapshot(store, DURING_PAUSE)}

    assert pointer_moved(watched_runs(store, PROJECT, [continuation]), snapshots) == []
    # The same snapshot does count against a run that was in flight at the time.
    assert pointer_moved(watched_runs(store, PROJECT, [reread]), snapshots) != []
