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

from amoeba.runner.dispatch.checkout_check import Block, DispatchCheck, Ok
from amoeba.runner.dispatch.facts import SliceDispatchFacts
from amoeba.runner.intent.governance import DesiredStateIndex
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.project_config import PROJECT_DEFAULTS, ProjectSettings
from amoeba.runner.resolutions.vocabulary import ResumeCause
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
    ``journal_extra`` is evidence written into the entry's parameters beside the
    launch's own (the merge policy, the target, the pre-dispatch check; slice 128).
    """

    node_id: str
    pipeline: str
    params: Mapping[str, str]
    checkout: Path
    run_id: str | None = None
    reissue_of: str | None = None
    journal_extra: Mapping[str, object] = field(default_factory=dict[str, object])


@dataclass(frozen=True)
class ResumeRun:
    """Resume a run: a PM's ``resume``, or an automatic retry (D5, D6).

    ``continues`` is the entry whose run it resumes. For ``cause`` ``resolution``,
    ``resolution`` is the blocked state whose decision it carries out; a ``transient``
    resume has none. ``instructions`` are an automatic resume's own text, passed to
    Squadron when set; a resolution resume's text stays in the resolution slot. The
    run id is the continued one.
    """

    node_id: str
    run_id: str
    continues: str
    resolution: str | None
    checkout: Path
    cause: ResumeCause = field(kw_only=True)
    instructions: str | None = field(default=None, kw_only=True)
    #: Evidence written into the continuation entry's parameters (slice 128, D5).
    journal_extra: Mapping[str, object] = field(default_factory=dict[str, object])

    def __post_init__(self) -> None:
        if self.cause is ResumeCause.RESOLUTION and self.resolution is None:
            raise ValueError("a resolution resume names the resolution it carries out")


@dataclass(frozen=True)
class BlockDispatch:
    """Block a step on a human because its pre-dispatch check said not to go ahead.

    Store-only: no journal entry (slice 128, D5).
    """

    node_id: str
    block: Block


#: The closed set of things a planner may ask for.
type Action = LaunchRun | ResumeRun | BlockDispatch


@dataclass(frozen=True)
class ProjectView:
    """Everything a planner may look at for one project, frozen.

    ``tree`` is the project's lifecycle tree, built after reconcile; it holds every
    node. ``desired`` is the project's desired-state rows, read once for the tick.
    ``current_slices`` are the ready slices the PM drives and has not held (D6);
    :func:`decide` refuses an action on any other node. ``ready_unbusy`` is the
    wider ready set, kept for slice 125 to narrow.
    ``link_probes`` maps a Context Forge link to whether its probe passed in
    this process lifetime. ``dispatch`` holds the dispatch facts of each current
    pipeline step, by node id, and ``checkout_holders`` names, for each checkout a
    pipeline already holds (D4), the nodes that hold it, so a step's own continuation
    can act in a checkout held only by itself (slice 127). Both are empty for a view
    that dispatches nothing. ``dispatch_checks`` holds this tick's pre-dispatch result
    for each candidate, by node id (D5); a node with no entry has no result.
    ``settings`` are the project's: its pipeline and parameters (slice 132, D2).
    """

    project_id: str
    now: datetime
    tree: LifecycleTree
    in_flight: tuple[InFlightRun, ...]
    link_probes: Mapping[str, bool]
    desired: DesiredStateIndex
    current_slices: Sequence[Node]
    dispatch: Mapping[str, SliceDispatchFacts] = field(
        default_factory=dict[str, SliceDispatchFacts]
    )
    checkout_holders: Mapping[Path, frozenset[str]] = field(
        default_factory=dict[Path, frozenset[str]]
    )
    dispatch_checks: Mapping[str, DispatchCheck] = field(
        default_factory=dict[str, DispatchCheck]
    )
    settings: ProjectSettings = PROJECT_DEFAULTS

    def ready_unbusy(self) -> list[Node]:
        """Ready slices (``tree.ready_slices()``) with no run in flight.

        What a planner may start. "In flight" is an unresolved ``sq_run`` entry:
        ``in_flight`` holds every such entry the tick has not finished and
        resolved, which is the only kind of unresolved entry the Runner issues.
        """
        busy = {run.entry.node_id for run in self.in_flight}
        return [node for node in self.tree.ready_slices() if node.id not in busy]


class Planner(Protocol):
    """Proposes actions for a project. Pure: no I/O, no clock read."""

    def plan(self, view: ProjectView) -> Sequence[Action]:
        """Return the actions this planner wants taken for ``view``."""
        ...


def decide(view: ProjectView, planners: Sequence[Planner]) -> list[Action]:
    """Run the planners in order and return all their actions.

    Raises:
        ValueError: If an action names a node that is not one of
            ``view.current_slices`` (not driven, held, not ready, or unknown): the
            guard that makes drive and hold bind every planner (D7). Or if two
            actions name the same node: a node gets at most one action per tick.
            Neither is ever silently dropped; both are programming errors. Or if a
            ``LaunchRun`` or ``ResumeRun`` names a node with no passed pre-dispatch
            check (``Ok``) in ``view.dispatch_checks``: nothing may start Squadron
            work unchecked (slice 128, D5).
    """
    actions: list[Action] = []
    claimed: set[str] = set()
    current = {node.id for node in view.current_slices}
    for planner in planners:
        for action in planner.plan(view):
            if action.node_id not in current:
                raise ValueError(
                    f"action for node {action.node_id} in project "
                    f"{view.project_id} is not a current slice"
                )
            if action.node_id in claimed:
                raise ValueError(
                    f"more than one action for node {action.node_id} in project "
                    f"{view.project_id}"
                )
            if isinstance(action, LaunchRun | ResumeRun) and not isinstance(
                view.dispatch_checks.get(action.node_id), Ok
            ):
                raise ValueError(
                    f"{type(action).__name__} for node {action.node_id} in project "
                    f"{view.project_id} has no passed pre-dispatch check"
                )
            claimed.add(action.node_id)
            actions.append(action)
    return actions
