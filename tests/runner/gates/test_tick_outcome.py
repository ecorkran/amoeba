"""D2 at tick level: a completed run is recorded with its observation, or deferred."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from amoeba.process import RunOutcome, RunOutcomeDocument
from amoeba.runner.gates.outcome_record import GATE_POSITION, OBS_DESIGN_PATH, OBS_GATE
from amoeba.runner.ingest.record import RESULT_CHECK_IDS, RESULT_OUTCOME_OBSERVATION
from amoeba.runner.launch import log_paths
from amoeba.runner.lifecycle.plan_read import CF_KEY_REVIEW_GATE_EFFECTIVE_DATE
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import PARAM_RUN_ID, JournalEntry, Node, Store
from runner.dispatch.tick_rig import DispatchRig
from runner.gate_rig import (
    config_knobs,
    git_checkout,
    single_status_knobs,
    status_fixture,
    write_design,
    write_slice_list,
)

DESIGN = "project-documents/user/slices/128-slice.gates.md"
SLICE_INDEX = 125  # an index the stub's CF state can point at


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    yield DispatchRig(tmp_path, store)


def _arrange(rig: DispatchRig, tmp_path: Path, status: str) -> Node:
    """A launched ``tasks`` step whose CF answers come from the stub ``cf``."""
    slice_node, node = rig.slice_and_step("gates", SLICE_INDEX, LifecycleStep.TASKS)
    assert slice_node.parent_id is not None
    initiative = rig.store.get_node(slice_node.parent_id)
    assert initiative is not None and initiative.cf.index is not None
    checkout = git_checkout(rig.world.root)
    write_design(checkout, DESIGN)
    knobs = {
        **write_slice_list(
            tmp_path / "plan", initiative.cf.index, {SLICE_INDEX: DESIGN}
        ),
        **single_status_knobs(
            status_fixture(tmp_path / "status.json", status, SLICE_INDEX)
        ),
        **config_knobs(tmp_path, {CF_KEY_REVIEW_GATE_EFFECTIVE_DATE: ""}),
    }
    rig.tick_rig.gate_run = rig.world.run(knobs)
    rig.tick()  # the pointer write
    rig.tick()  # the launch
    return node


def _finish_run(rig: DispatchRig, node: Node, answers: int = 1) -> JournalEntry:
    """The run ends as ``completed``; ``answers`` polls will say so."""
    entry = rig.run_of(node)
    run_id = str(entry.parameters[PARAM_RUN_ID])
    rig.tick_rig.tracker.confirm(entry.id)
    log_paths(rig.tick_rig.supervisor_dir, entry.id).stderr.write_text(
        f"run_id={run_id}\n"
    )
    for _ in range(answers):
        rig.tick_rig.poll.answers.append(
            RunOutcomeDocument.model_validate(
                {
                    "run_id": run_id,
                    "outcome": RunOutcome.COMPLETED.value,
                    "status": RunOutcome.COMPLETED.value,
                }
            )
        )
    rig.tick_rig.clock.seconds += 20.0
    return entry


def _checks(rig: DispatchRig, node: Node) -> list[str]:
    assert node.parent_id is not None
    return [c.name for c in rig.store.checks("demo", node_id=node.parent_id)]


def test_a_completed_p5_records_two_checks_on_the_slice_node_and_the_observation(
    rig: DispatchRig, tmp_path: Path
) -> None:
    node = _arrange(rig, tmp_path, "pending_review_tasks")
    entry = _finish_run(rig, node)

    rig.tick()

    done = rig.store.journal_entry(entry.id)
    assert done is not None and done.is_resolved and done.result is not None
    stored = done.result[RESULT_OUTCOME_OBSERVATION]
    assert isinstance(stored, dict)
    assert stored[OBS_GATE][GATE_POSITION] == "AT_TASKS_GATE"
    assert stored[OBS_DESIGN_PATH] == DESIGN
    assert sorted(_checks(rig, node)) == ["ungate_effective_date", "ungate_review_none"]
    assert len(done.result[RESULT_CHECK_IDS]) == 2  # type: ignore[arg-type]


def test_a_cut_off_before_the_observation_leaves_the_entry_unresolved_then_records_once(
    rig: DispatchRig, tmp_path: Path
) -> None:
    node = _arrange(rig, tmp_path, "pending_review_tasks")
    entry = _finish_run(rig, node, answers=2)
    clock = rig.tick_rig.clock
    real_run = rig.tick_rig.gate_run
    spent: list[bool] = []

    def cut_off_after_first_call(
        argv: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if not spent:
            spent.append(True)
            clock.seconds += 10_000_000.0  # the tick's budget is gone
        return real_run(argv, **kwargs)

    rig.tick_rig.gate_run = cut_off_after_first_call

    rig.tick()

    still_open = rig.store.journal_entry(entry.id)
    assert still_open is not None and not still_open.is_resolved
    assert _checks(rig, node) == []
    assert rig.tick_rig.tracker.get(entry.id) is not None, "still tracked"

    rig.tick_rig.gate_run = real_run
    rig.tick_rig.deadline = clock.seconds + 1_000_000.0
    rig.tick()

    done = rig.store.journal_entry(entry.id)
    assert done is not None and done.is_resolved
    assert sorted(_checks(rig, node)) == ["ungate_effective_date", "ungate_review_none"]
    assert len(rig.store.checks("demo")) == 2
