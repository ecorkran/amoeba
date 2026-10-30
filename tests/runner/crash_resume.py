"""Stage a paused run and a PM's ``resume`` for the resume crash proofs (slice 127).

Before any process starts, the dispatch harness's one step gets a finished, routed,
paused run in the stub's state and a ``resume`` resolution the Runner has yet to
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
    """What the proofs assert against; ``blocked_state_id`` is empty without a PM."""

    node_id: str
    run_id: str
    paused_entry_id: str
    blocked_state_id: str


def stage_paused_retry(harness: CrashHarness) -> StagedResume:
    """A paused run in the stub, a routed entry for it, and a ``resume`` resolution."""
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
            store, node, "resume", INSTRUCTIONS, project_id=PROJECT
        )
    write_outcome_document(harness.home, paused_document(run_id))
    return StagedResume(node_id, run_id, entry.id, blocked_id)


def stage_transient_failure(harness: CrashHarness) -> StagedResume:
    """A run that stopped on a ``stall``, resolved and recorded, in the stub's state.

    No resolution is staged: the first tick of the first process resumes it on its
    own (slice 132, D5).
    """
    [node_id] = harness.node_ids
    with Store.open(project_store_path(harness.supervisor_dir, PROJECT)) as store:
        node = store.get_node(node_id)
        assert node is not None
        failed_at = "design-0"
        entry = finished_run(
            store,
            node,
            RunOutcome.FAILED,
            document=_stalled_document("placeholder", failed_at),
            checkout=str(harness.checkout),
        )
        run_id = str(entry.parameters["run_id"])
    write_outcome_document(harness.home, _stalled_document(run_id, failed_at))
    return StagedResume(node_id, run_id, entry.id, "")


def _stalled_document(run_id: str, step: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "outcome": RunOutcome.FAILED.value,
        "status": RunOutcome.FAILED.value,
        "failure": {"kind": "stall", "step": step, "message": "no progress"},
    }
