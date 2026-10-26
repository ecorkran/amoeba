"""The decide stage: a pure function from a frozen view to actions.

A :class:`Planner` is the one seam (D1). It receives only the
:class:`ProjectView`, including ``now``, and does no I/O, so a decision can be
recomputed from the same view. Later slices add planners and view fields; they
do not add a stage registry.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from amoeba.runner.dispatch.checkout import Checkout
from amoeba.runner.dispatch.facts import StepDispatchFacts
from amoeba.runner.intent.governance import DesiredStateIndex
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.resolutions.vocabulary import Continuation
from amoeba.store import JournalEntry, Node


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
    """Start ``pipeline`` in ``checkout`` for a node.

    ``run_id`` and ``reissue_of`` are set together for a reissue (D9): the run id of
    an attempt that never started, and the id of the entry that attempt was.
    """

    node_id: str
    pipeline: str
    params: Mapping[str, str]
    checkout: Path
    run_id: str | None = None
    reissue_of: str | None = None


@dataclass(frozen=True)
class BlockHumanStep:
    """Block a ready human step on a person (D9). Store-only: no journal entry."""

    node_id: str


@dataclass(frozen=True)
class WriteSlicePointer:
    """Point ``checkout``'s CF at a slice (D2); the launch follows on a later tick."""

    node_id: str
    cf_project_id: str
    slice_index: int
    checkout: Checkout
    #: The blocked state id of the ``rerun`` this write carries out (slice 127, D5).
    resolution: str | None = None


@dataclass(frozen=True)
class ResumeRun:
    """Resume a paused run for an applied ``retry`` or ``accept`` (slice 127, D4).

    ``continues`` is the entry whose run it resumes, and ``resolution`` the blocked
    state whose decision it carries out. The run id is the continued one.
    """

    node_id: str
    run_id: str
    decision: Continuation
    continues: str
    resolution: str
    checkout: Path


@dataclass(frozen=True)
class ObserveRun:
    """Observe a run the PM moved by hand, after an applied ``handled`` (D4)."""

    node_id: str
    run_id: str
    continues: str
    resolution: str
    checkout: Path


#: The closed set of things a planner may ask for.
type Action = LaunchRun | BlockHumanStep | WriteSlicePointer | ResumeRun | ObserveRun


@dataclass(frozen=True)
class ProjectView:
    """Everything a planner may look at for one project, frozen.

    ``tree`` is the project's lifecycle tree, built after reconcile; it holds every
    node. ``desired`` is the project's desired-state rows, read once for the tick.
    ``current_steps`` are the ready steps the PM drives and has not held (D6);
    :func:`decide` refuses an action on any other node. ``ready_unbusy`` is the
    wider ready set, kept for slice 125 to narrow.
    ``link_probes`` maps a Context Forge link to whether its probe passed in
    this process lifetime. ``dispatch`` holds the dispatch facts of each current
    pipeline step, by node id, and ``checkout_holders`` names, for each checkout a
    pipeline already holds (D4), the nodes that hold it, so a step's own continuation
    can act in a checkout held only by itself (slice 127). Both are empty for a view
    that dispatches nothing.
    """

    project_id: str
    now: datetime
    tree: LifecycleTree
    in_flight: tuple[InFlightRun, ...]
    link_probes: Mapping[str, bool]
    desired: DesiredStateIndex
    current_steps: Sequence[Node]
    dispatch: Mapping[str, StepDispatchFacts] = field(
        default_factory=dict[str, StepDispatchFacts]
    )
    checkout_holders: Mapping[Path, frozenset[str]] = field(
        default_factory=dict[Path, frozenset[str]]
    )

    def ready_unbusy(self) -> list[Node]:
        """Ready steps (``tree.ready_steps()``) with no run in flight.

        What a planner may start. "In flight" is an unresolved ``sq_run`` entry:
        ``in_flight`` holds every such entry the tick has not finished and
        resolved, which is the only kind of unresolved entry the Runner issues.
        """
        busy = {run.entry.node_id for run in self.in_flight}
        return [node for node in self.tree.ready_steps() if node.id not in busy]


class Planner(Protocol):
    """Proposes actions for a project. Pure: no I/O, no clock read."""

    def plan(self, view: ProjectView) -> Sequence[Action]:
        """Return the actions this planner wants taken for ``view``."""
        ...


def decide(view: ProjectView, planners: Sequence[Planner]) -> list[Action]:
    """Run the planners in order and return all their actions.

    Raises:
        ValueError: If an action names a node that is not one of
            ``view.current_steps`` (not driven, held, not ready, or unknown): the
            guard that makes drive and hold bind every planner (D7). Or if two
            actions name the same node: a node gets at most one action per tick.
            Neither is ever silently dropped; both are programming errors.
    """
    actions: list[Action] = []
    claimed: set[str] = set()
    current = {node.id for node in view.current_steps}
    for planner in planners:
        for action in planner.plan(view):
            if action.node_id not in current:
                raise ValueError(
                    f"action for node {action.node_id} in project "
                    f"{view.project_id} is not a current step"
                )
            if action.node_id in claimed:
                raise ValueError(
                    f"more than one action for node {action.node_id} in project "
                    f"{view.project_id}"
                )
            claimed.add(action.node_id)
            actions.append(action)
    return actions
