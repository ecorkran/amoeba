"""Builders for the hold and planner tests: entries, facts, nodes and a view."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from itertools import count
from pathlib import Path

from amoeba.runner.decide import ProjectView
from amoeba.runner.dispatch.checkout import Checkout, CheckoutUnresolved
from amoeba.runner.dispatch.facts import SortKey, StepDispatchFacts
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.ingest.record import RESULT_OUTCOME
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.runner.lifecycle.steps import LifecycleStep, step_rank
from amoeba.runner.lifecycle.tree import LifecycleTree
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
    step: LifecycleStep = LifecycleStep.TASKS,
    slice_index: int = 125,
    initiative_index: int = 120,
    reissue_of: JournalEntry | None = None,
    resolution: BlockedState | None = None,
    continues: JournalEntry | None = None,
) -> StepDispatchFacts:
    """Dispatch facts for a step; the sort key follows the LLD's order."""
    resolved = (
        Checkout(checkout, None) if isinstance(checkout, Path) else checkout
    ) or CheckoutUnresolved("test")
    sort_key: SortKey = (initiative_index, slice_index, step_rank(step))
    return StepDispatchFacts(
        step=step,
        state=state,
        checkout=resolved,
        slice_index=slice_index,
        cf_project_id=CF_PROJECT,
        sort_key=sort_key,
        reissue_of=reissue_of,
        resolution=resolution,
        continues=continues,
    )


def view_of(
    steps: dict[str, StepDispatchFacts],
    held: Iterable[Path] = (),
    current: Iterable[str] | None = None,
    holders: Mapping[Path, frozenset[str]] | None = None,
) -> ProjectView:
    """A view whose current steps are ``current`` (default: all of ``steps``).

    ``holders`` names who holds each held checkout; its checkouts are held too.
    """
    names = list(steps) if current is None else list(current)
    named = dict(holders or {})
    return replace(
        view_for(LifecycleTree(())),
        current_steps=tuple(node(name) for name in names),
        dispatch=steps,
        held_checkouts=frozenset(held) | frozenset(named),
        checkout_holders=named,
    )
