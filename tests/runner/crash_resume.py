"""Stage a paused run and a PM's ``retry`` for the resume crash proofs (slice 127).

Before any process starts, the dispatch harness's one step gets a finished, routed,
paused run in the stub's state and a ``retry`` resolution the Runner has yet to
answer, so the first tick of the first process acknowledges it and resumes the run.
"""

from __future__ import annotations

from dataclasses import dataclass

from sq_stub import write_outcome_document

from amoeba.process import RunOutcome
from amoeba.store import Store, project_store_path
from runner.crash_harness import PROJECT, CrashHarness
from runner.resolutions.resolution_support import (
    block_and_resolve,
    finished_run,
    paused_document,
)

INSTRUCTIONS = "Address the schema concerns only."


@dataclass(frozen=True)
class StagedResume:
    """What the proofs assert against."""

    node_id: str
    run_id: str
    paused_entry_id: str
    blocked_state_id: str


def stage_paused_retry(harness: CrashHarness) -> StagedResume:
    """A paused run in the stub, a routed entry for it, and a ``retry`` resolution."""
    [node_id] = harness.node_ids
    with Store.open(project_store_path(harness.supervisor_dir, PROJECT)) as store:
        node = store.get_node(node_id)
        assert node is not None
        entry = finished_run(
            store,
            node,
            RunOutcome.PAUSED,
            document=paused_document("placeholder"),
            checkout=str(harness.checkout),
        )
        run_id = str(entry.parameters["run_id"])
        blocked_id = block_and_resolve(
            store, node, "retry", INSTRUCTIONS, project_id=PROJECT
        )
    write_outcome_document(harness.home, paused_document(run_id))
    return StagedResume(node_id, run_id, entry.id, blocked_id)
