"""The resolution stage in the project tick: first, and contained per node."""

from __future__ import annotations

from pathlib import Path

import pytest
from sq_run_fixtures import sq_run_parameters

from amoeba.process import RunOutcome
from amoeba.runner.budget import TickResult
from amoeba.runner.resolutions.vocabulary import ResolutionRejection
from amoeba.store import CommandKind, JournalOutcome, ResolutionOutcome, Store
from runner.observe_support import Child, document
from runner.resolutions.resolution_support import (
    block_and_resolve,
    design_step,
)
from runner.tick_support import PROJECT, Rig


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Rig:
    built = Rig(tmp_path, store)
    built.planners = ()
    return built


def test_a_resolution_is_acknowledged_in_the_next_tick_before_any_planner_sees_it(
    rig: Rig, store: Store
) -> None:
    node = design_step(store)
    state_id = block_and_resolve(store, node, "resume")
    seen: list[bool] = []

    class Spy:
        def plan(self, view: object) -> list[object]:
            seen.append(store.pending_resolutions(PROJECT) == [])
            return []

    rig.planners = (Spy(),)

    result, tick = rig.tick()

    assert result is TickResult.COMPLETE and tick.wrote
    state = store.blocked_state(state_id)
    assert state is not None and state.runner_outcome is ResolutionOutcome.APPLIED
    assert seen == [True]


def test_poisoned_resolution_is_contained(
    rig: Rig, store: Store, tmp_path: Path
) -> None:
    """A rejected resolution does not stop the others; the tick goes on."""
    stale = design_step(store)
    rejected_id = block_and_resolve(store, stale, "retry")
    running = design_step(store)
    entry = store.journal_issue(
        running.id,
        kind=CommandKind.SQ_RUN,
        parameters=sq_run_parameters(
            {"pipeline": "P4", "params": {}, "checkout": str(tmp_path)},
            run_id="run-live",
        ),
    )
    rig.tracker.track(entry.id, Child(None))
    rig.tracker.confirm(entry.id)
    rig.poll.answers.append(document("run-live", RunOutcome.COMPLETED))

    result, _ = rig.tick()

    assert result is TickResult.COMPLETE
    rejected = store.blocked_state(rejected_id)
    assert rejected is not None
    assert rejected.runner_code == ResolutionRejection.UNKNOWN_DECISION
    ingested = store.journal_entry(entry.id)
    assert ingested is not None and ingested.outcome is JournalOutcome.COMPLETED
