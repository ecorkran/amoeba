"""Builders for the hold and planner tests: entries, facts, nodes and a view."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from itertools import count
from pathlib import Path

from amoeba.runner.decide import ProjectView
from amoeba.runner.dispatch.checkout import Checkout, CheckoutUnresolved
from amoeba.runner.dispatch.facts import SliceDispatchFacts, SortKey
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.gates.predispatch import DispatchCheck, Ok
from amoeba.runner.ingest.record import RESULT_OUTCOME
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.project_config import ProjectSettings
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_RUN_ID,
    BlockedState,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
    Node,
    NodeKind,
    NodeStatus,
)
from runner.tick_support import view_for

PROJECT = "demo"
CF_PROJECT = "cf-a"
FIRST = Path("/work/amoeba")
SECOND = Path("/work/amoeba-2")

_ENTRY_IDS = count(1)

#: What a passed pre-dispatch check says, as the planners record it on a launch.
OK_EVIDENCE: Mapping[str, object] = {
    "branch": "main",
    "head": "abc123",
    "target": "main",
    "gate_status": None,
    "gate_review_type": None,
}
OK = Ok(OK_EVIDENCE)


def node(node_id: str) -> Node:
    """A bare runnable step node; the planner reads only its id."""
    return Node(
        id=node_id,
        project_id=PROJECT,
        kind=NodeKind.PHASE_OR_ARTIFACT,
        status=NodeStatus.RUNNABLE,
        title=node_id,
    )


def entry(
    kind: CommandKind,
    node_id: str,
    checkout: Path | None = FIRST,
    outcome: JournalOutcome | None = None,
    *,
    outcome_text: str | None = None,
    resolved_by: JournalResolver = JournalResolver.ISSUER,
    run_id: str | None = None,
) -> JournalEntry:
    """A journal entry; ``outcome_text`` is the run outcome in a resolved result."""
    number = next(_ENTRY_IDS)
    parameters: dict[str, object] = {
        PARAM_PIPELINE: "P5",
        PARAM_PARAMS: {"slice": "125"},
        PARAM_RUN_ID: run_id or f"run-{number}",
    }
    if checkout is not None:
        parameters[PARAM_CHECKOUT] = str(checkout)
    return JournalEntry(
        id=f"entry-{number}",
        project_id=PROJECT,
        node_id=node_id,
        kind=kind,
        parameters=parameters,
        outcome=outcome,
        resolved_by=None if outcome is None else resolved_by,
        result=None if outcome_text is None else {RESULT_OUTCOME: outcome_text},
    )


def facts(
    state: DispatchState,
    checkout: Path | CheckoutUnresolved | None = FIRST,
    *,
    slice_index: int = 125,
    initiative_index: int = 120,
    reissue_of: JournalEntry | None = None,
    resolution: BlockedState | None = None,
    continues: JournalEntry | None = None,
) -> SliceDispatchFacts:
    """Dispatch facts for a slice; the sort key follows the LLD's order."""
    resolved = (
        Checkout(checkout, None) if isinstance(checkout, Path) else checkout
    ) or CheckoutUnresolved("test")
    sort_key: SortKey = (initiative_index, slice_index)
    return SliceDispatchFacts(
        state=state,
        checkout=resolved,
        slice_index=slice_index,
        cf_project_id=CF_PROJECT,
        sort_key=sort_key,
        reissue_of=reissue_of,
        resolution=resolution,
        continues=continues,
    )


#: The pipeline the test projects are configured with.
TEST_PIPELINE = "p456"


def view_of(
    steps: dict[str, SliceDispatchFacts],
    held: Iterable[Path] = (),
    current: Iterable[str] | None = None,
    holders: Mapping[Path, frozenset[str]] | None = None,
    checks: Mapping[str, DispatchCheck] | None = None,
    settings: ProjectSettings | None = None,
) -> ProjectView:
    """A view whose current slices are ``current`` (default: all of ``steps``).

    ``held`` checkouts are held by an unnamed node; ``holders`` names who holds each.
    ``checks`` are the pre-dispatch results; by default every current step has passed
    (``OK``), so a planner test sees a launch unless it says otherwise. ``settings``
    default to a project configured with ``TEST_PIPELINE``.
    """
    names = list(steps) if current is None else list(current)
    named = {path: frozenset({"unnamed-holder"}) for path in held}
    named.update(holders or {})
    return replace(
        view_for(LifecycleTree(())),
        current_slices=tuple(node(name) for name in names),
        dispatch=steps,
        checkout_holders=named,
        dispatch_checks={name: OK for name in names} if checks is None else checks,
        settings=ProjectSettings(pipeline=TEST_PIPELINE)
        if settings is None
        else settings,
    )
