"""The merge observation under load: its reads stop at the tick's deadline.

Many slices await a human merge and each costs two subprocess reads (``cf config get``
and ``git merge-base``), as they do on a slow disk. The asserted properties are
counts and bounds, not a speed claim:

* a pass the deadline cuts off starts no call after the deadline, so it ends within
  one call of it;
* with time enough, every slice gets its observation.

Measured 20261027 on the development machine (Darwin 25.5.0, Python 3.13):
60 slices, 10 ms per read, 0.3 s deadline: the cut-off pass makes about 25 reads and
ends at 0.31 s; the unbounded pass makes 120 and observes all 60 in about 1.5 s.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from amoeba.process import RunOutcome
from amoeba.runner.budget import TickBudget
from amoeba.runner.faults import TickFaults
from amoeba.runner.gates.merge import observe_merges
from amoeba.runner.gates.merge_observation import NotMerged
from amoeba.runner.ingest.record import RESULT_OUTCOME, RESULT_OUTCOME_OBSERVATION
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import (
    PARAM_CHECKOUT,
    CFReference,
    CommandKind,
    JournalOutcome,
    NodeKind,
    NodeStatus,
    Store,
)

PROJECT = "demo"
SLICE_COUNT = 60
READ_COST_SECONDS = 0.01
DEADLINE_SECONDS = 0.3
CALL_TIMEOUT_SECONDS = 20.0
FIRST_INDEX = 200

#: A pass may overrun its deadline by one call and scheduling noise.
SLACK_SECONDS = 1.0


class Host:
    stop_requested = False


class SlowReads:
    """A ``cf``/``git`` runner whose every call costs time and says "not merged"."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(
        self, argv: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls += 1
        time.sleep(READ_COST_SECONDS)
        if argv[0] == "git":
            return subprocess.CompletedProcess(argv, 1, "", "")
        return subprocess.CompletedProcess(argv, 0, '{"value": ""}', "")


def _slice_awaiting_merge(store: Store, index: int, checkout: Path) -> None:
    slice_node = store.create_node(
        project_id=PROJECT,
        kind=NodeKind.SLICE,
        title=f"slice {index}",
        cf=CFReference(project="cf-a", index=index),
    )
    implementation = store.create_node(
        project_id=PROJECT,
        kind=NodeKind.PHASE_OR_ARTIFACT,
        title=LifecycleStep.IMPLEMENTATION.value,
        parent_id=slice_node.id,
        cf=CFReference(project="cf-a", phase=LifecycleStep.IMPLEMENTATION.value),
    )
    store.create_node(
        project_id=PROJECT,
        kind=NodeKind.PHASE_OR_ARTIFACT,
        title=LifecycleStep.MERGE.value,
        parent_id=slice_node.id,
        cf=CFReference(project="cf-a", phase=LifecycleStep.MERGE.value),
    )
    issued = store.journal_issue(
        implementation.id,
        kind=CommandKind.SQ_RUN,
        parameters={
            "pipeline": "P6",
            "params": {},
            "run_id": f"run-{index}",
            PARAM_CHECKOUT: str(checkout),
        },
    )
    store.journal_resolve(
        issued.id,
        outcome=JournalOutcome.COMPLETED,
        result={
            RESULT_OUTCOME: RunOutcome.COMPLETED.value,
            RESULT_OUTCOME_OBSERVATION: {
                "git": {"branch": f"{index}-slice.x", "head": "abc123"}
            },
        },
    )
    store.update_node_status(implementation.id, NodeStatus.DONE)


def test_the_merge_reads_stop_at_the_deadline_and_finish_given_time(
    tmp_path: Path, store: Store
) -> None:
    for offset in range(SLICE_COUNT):
        _slice_awaiting_merge(store, FIRST_INDEX + offset, tmp_path)
    tree = LifecycleTree(store.nodes_for_project(PROJECT))

    cut_reads = SlowReads()
    started = time.monotonic()
    budget = TickBudget(started + DEADLINE_SECONDS, Host(), time.monotonic)
    cut = observe_merges(
        store, tree, PROJECT, budget, cut_reads, CALL_TIMEOUT_SECONDS, TickFaults()
    )
    cut_elapsed = time.monotonic() - started

    full_reads = SlowReads()
    started = time.monotonic()
    unbounded = TickBudget(started + 1_000.0, Host(), time.monotonic)
    full = observe_merges(
        store, tree, PROJECT, unbounded, full_reads, CALL_TIMEOUT_SECONDS, TickFaults()
    )
    full_elapsed = time.monotonic() - started

    print(
        f"cut: reads={cut_reads.calls} {cut_elapsed:.2f}s; "
        f"full: reads={full_reads.calls} {full_elapsed:.2f}s"
    )
    assert cut.cut_off, "the deadline cut the pass off"
    assert cut_elapsed <= DEADLINE_SECONDS + READ_COST_SECONDS + SLACK_SECONDS
    assert cut_reads.calls <= DEADLINE_SECONDS / READ_COST_SECONDS + 1, "no late call"
    assert not full.cut_off
    assert len(full.observations) == SLICE_COUNT
    assert all(isinstance(o, NotMerged) for o in full.observations.values())
