"""Stage a step with a finished run and a PM's resolution, for the resolution tests.

The run is not simulated: the entry is journaled and resolved with the result shape
125's ingestion leaves, so the stage reads what it reads in production.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime

from sq_run_fixtures import sq_run_parameters

from amoeba.process import RunOutcome
from amoeba.runner.ingest.record import (
    RESULT_OUTCOME,
    RESULT_OUTCOME_DOCUMENT,
    RESULT_RUN_ID,
    RESULT_STATUS,
)
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import (
    BlockedKind,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    Node,
    Store,
    SubmissionKind,
    sql_journal,
)
from amoeba.store.inbox_models import (
    RESOLUTION_BLOCKED_STATE_ID,
    RESOLUTION_DECISION,
    RESOLUTION_DETAIL,
    RESOLUTION_INSTRUCTIONS,
)
from runner.tick_support import PROJECT, ready_slice

PAUSED_AT = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
_RUN_PARAMETERS: Mapping[str, object] = {
    "pipeline": "P4",
    "params": {},
    "project": "p",
    "expected": "x",
    "checkout": "/work/p",
}

_counter = [0]


def design_step(store: Store) -> Node:
    """A ready slice under a fresh initiative (the unit of work, slice 132)."""
    _counter[0] += 1
    return ready_slice(store, PROJECT, f"slice-{_counter[0]}")


def paused_document(
    run_id: str, *, kind: str | None = "loop_exhausted", is_loop: object = True
) -> dict[str, object]:
    """A paused run's outcome document, with a checkpoint."""
    return {
        "run_id": run_id,
        "outcome": RunOutcome.PAUSED.value,
        "checkpoint": {
            "kind": kind,
            "is_loop": is_loop,
            "paused_at": PAUSED_AT.isoformat(),
        },
    }


def finished_run(
    store: Store,
    node: Node,
    outcome: RunOutcome,
    *,
    document: Mapping[str, object] | None = None,
    extra: Mapping[str, object] | None = None,
    routed: bool = True,
    checkout: str | None = None,
) -> JournalEntry:
    """Journal an ``sq_run`` on the node and resolve it with ``outcome``.

    Resolving as the issuer flags the entry as awaiting routing; ``routed`` clears
    the flag, as a routing decision would, so the step is not ``unresolvable``.
    """
    run_id = f"run-{node.id[:8]}"
    entry = store.journal_issue(
        node.id,
        kind=CommandKind.SQ_RUN,
        parameters=sq_run_parameters(
            {**_RUN_PARAMETERS, **({} if checkout is None else {"checkout": checkout})},
            run_id=run_id,
        ),
    )
    result: dict[str, object] = {
        RESULT_RUN_ID: run_id,
        RESULT_OUTCOME: outcome.value,
        RESULT_STATUS: outcome.value,
        RESULT_OUTCOME_DOCUMENT: document,
    }
    result.update(extra or {})
    journal_outcome = (
        JournalOutcome.COMPLETED
        if outcome is RunOutcome.COMPLETED
        else JournalOutcome.FAILED
    )
    resolved = store.journal_resolve(entry.id, outcome=journal_outcome, result=result)
    if routed:
        with sqlite3.connect(store.path) as connection:
            connection.execute(sql_journal.CLEAR_AWAITS_ROUTING, (entry.id,))
        return replace(resolved, awaits_routing=False)
    return resolved


def block_and_resolve(
    store: Store,
    node: Node,
    decision: str | None = None,
    instructions: str | None = None,
    *,
    project_id: str = PROJECT,
) -> str:
    """Block the node on a human and submit the PM's resolution; the blocked id."""
    blocked = store.block(node.id, kind=BlockedKind.HUMAN, context="decide")
    return resolve_block(store, blocked.id, decision, instructions, project_id)


def resolve_block(
    store: Store,
    blocked_state_id: str,
    decision: str | None = None,
    instructions: str | None = None,
    project_id: str = PROJECT,
) -> str:
    """Submit the PM's resolution of an existing open block; its id."""
    payload: dict[str, object] = {
        RESOLUTION_BLOCKED_STATE_ID: blocked_state_id,
        RESOLUTION_DETAIL: "go",
    }
    if decision is not None:
        payload[RESOLUTION_DECISION] = decision
    if instructions is not None:
        payload[RESOLUTION_INSTRUCTIONS] = instructions
    store.apply_submission(
        submission_id=f"sub-{blocked_state_id}",
        project_id=project_id,
        kind=SubmissionKind.RESOLUTION,
        submitted_by="pm",
        submitted_at=PAUSED_AT,
        payload=payload,
    )
    return blocked_state_id


def tree_of(store: Store) -> LifecycleTree:
    return LifecycleTree(store.nodes_for_project(PROJECT))
