"""The decide stage: a pure function from a frozen view to actions.

A :class:`Planner` is the one seam (D1). It receives only the
:class:`ProjectView`, including ``now``, and does no I/O, so a decision can be
recomputed from the same view. Later slices add planners and view fields; they
do not add a stage registry.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import JournalEntry


class RunState(StrEnum):
    """Where an in-flight run is in its life, as the last observation saw it."""

    LAUNCHING = "launching"
    RUNNING = "running"
    FINISHED = "finished"
    FAULT = "fault"


@dataclass(frozen=True)
class InFlightRun:
    """An unresolved ``sq_run`` entry and what observation made of it."""

    entry: JournalEntry
    run_id: str
    state: RunState


@dataclass(frozen=True)
class LaunchRun:
    """Start ``pipeline`` in ``checkout`` for a node."""

    node_id: str
    pipeline: str
    params: Mapping[str, str]
    checkout: Path


#: The closed set of things a planner may ask for. 125 adds ``WriteCFPointer``.
type Action = LaunchRun


@dataclass(frozen=True)
class ProjectView:
    """Everything a planner may look at for one project, frozen.

    ``tree`` is the project's lifecycle tree, built after reconcile; it holds every
    node, so a planner narrows by status, ``ready_steps`` and ``in_flight`` itself.
    ``link_probes`` maps a Context Forge link to whether its probe passed in
    this process lifetime.
    """

    project_id: str
    now: datetime
    tree: LifecycleTree
    in_flight: tuple[InFlightRun, ...]
    link_probes: Mapping[str, bool]


class Planner(Protocol):
    """Proposes actions for a project. Pure: no I/O, no clock read."""

    def plan(self, view: ProjectView) -> Sequence[Action]:
        """Return the actions this planner wants taken for ``view``."""
        ...


def decide(view: ProjectView, planners: Sequence[Planner]) -> list[Action]:
    """Run the planners in order and return all their actions.

    Raises:
        ValueError: If two actions name the same node. A node gets at most one
            action per tick; a second is a programming error and is never
            silently dropped.
    """
    actions: list[Action] = []
    claimed: set[str] = set()
    for planner in planners:
        for action in planner.plan(view):
            if action.node_id in claimed:
                raise ValueError(
                    f"more than one action for node {action.node_id} in project "
                    f"{view.project_id}"
                )
            claimed.add(action.node_id)
            actions.append(action)
    return actions
