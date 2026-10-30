"""Build one tick's :class:`ProjectView` from the store and the observed runs.

Built after record and before routing (slice 126, D8), so what routing does is
first seen by the next tick's view. Held apart from ``tick.py`` to keep it short.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from amoeba.runner.decide import ProjectView
from amoeba.runner.dispatch.build_view import (
    DispatchView,
    block_unresolved,
    build_dispatch_view,
)
from amoeba.runner.intent.governance import DesiredStateIndex, current_steps
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.observed import ObservedRun
from amoeba.runner.project_config import MergePolicy
from amoeba.store import Node, Store


@dataclass(frozen=True)
class BuiltView:
    """The view, and whether building it wrote to the store."""

    view: ProjectView
    wrote: bool


def build_project_view(
    store: Store,
    project_id: str,
    now: datetime,
    runs: Sequence[ObservedRun],
    link_probes: Mapping[str, bool],
    desired: DesiredStateIndex,
    *,
    dispatching: bool,
    merge_policy: MergePolicy,
) -> BuiltView:
    """The facts the planners decide on, for ``project_id``."""
    tree = LifecycleTree(store.nodes_for_project(project_id))
    current = current_steps(tree, desired)
    dispatch, wrote = _dispatch_view(store, project_id, tree, current, dispatching)
    view = ProjectView(
        project_id=project_id,
        now=now,
        tree=tree,
        # Unresolved sq_run entries the tick did not finish: what ``ready_unbusy``
        # excludes (finished ones were resolved by ``finish.record`` above).
        in_flight=tuple(o.run for o in runs if o.finished is None),
        link_probes=link_probes,
        desired=desired,
        current_steps=current,
        dispatch=dispatch.facts,
        checkout_holders=dispatch.holders,
        merge_policy=merge_policy,
    )
    return BuiltView(view, wrote)


def _dispatch_view(
    store: Store,
    project_id: str,
    tree: LifecycleTree,
    current: Sequence[Node],
    dispatching: bool,
) -> tuple[DispatchView, bool]:
    """The dispatch facts, only when a dispatch planner is registered (D1).

    Without one nothing launches, so a step with no checkout is not a fault, and
    no step is blocked for it. Returns whether blocking unresolved steps wrote.
    """
    if not dispatching:
        return DispatchView({}, {}, ()), False
    dispatch = build_dispatch_view(
        store,
        project_id,
        tree,
        current,
        is_dir=Path.is_dir,
    )
    return dispatch, block_unresolved(store, dispatch.unresolved)
