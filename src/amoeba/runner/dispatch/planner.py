"""``DispatchPlanner``: launch or resume a pipeline in a free checkout (D3, D4).

Pure: it reads only the view's dispatch facts and held checkouts. For each current
pipeline step it proposes the one action its state calls for, and it proposes at most
one action per checkout per tick:

========================  =====================================================
state                     action
========================  =====================================================
``READY``                 ``LaunchRun``
``REISSUE``               ``LaunchRun`` repeating the attempt that never started
``AUTO_RESUME``           ``ResumeRun`` (transient), once the outcome is ready (D5)
``IN_FLIGHT``             nothing
========================  =====================================================

A held checkout offers nothing to a step, except an ``AUTO_RESUME`` held only by
itself: its own stopped run is what holds the checkout. Within a free checkout the
steps go by ``(initiative index, slice index, step rank)``. A checkout the snapshot
could not resolve gets nothing here: the tick blocks the step (D1).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from amoeba.runner.decide import (
    Action,
    BlockDispatch,
    LaunchRun,
    ProjectView,
    ResumeRun,
)
from amoeba.runner.dispatch.checkout import Checkout
from amoeba.runner.dispatch.facts import SliceDispatchFacts, SortKey
from amoeba.runner.dispatch.params import (
    PARAM_DISPATCH_CHECK,
    launch_params,
)
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.gates.predispatch import Block, Ok
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE, text_parameter
from amoeba.runner.project_config import ProjectSettings
from amoeba.runner.resolutions.vocabulary import (
    ResumeCause,
)
from amoeba.runner.supervise import recorded_document, resume_ready
from amoeba.store import PARAM_CHECKOUT, PARAM_RUN_ID, JournalEntry, Node

#: The states that start a pipeline; the others continue or wait.
_LAUNCHES = frozenset({DispatchState.READY, DispatchState.REISSUE})
_PLANNED = _LAUNCHES | {DispatchState.AUTO_RESUME}


class DispatchPlanner:
    """Plans launches and automatic resumes for the current pipeline steps."""

    def plan(self, view: ProjectView) -> Sequence[Action]:
        """At most one action per checkout, the best candidate in each."""
        best: dict[Path, tuple[SortKey, Node]] = {}
        for node in view.current_slices:
            facts = view.dispatch.get(node.id)
            if facts is None or not isinstance(facts.checkout, Checkout):
                continue
            if facts.state not in _PLANNED:
                continue
            path = facts.checkout.path
            if _held_by_another(view, path, node, facts.state):
                continue
            rank = facts.sort_key
            if path not in best or rank < best[path][0]:
                best[path] = (rank, node)
        ordered = sorted(best.values(), key=lambda pair: pair[0])
        actions = (_action(node, view.dispatch[node.id], view) for _, node in ordered)
        return [action for action in actions if action is not None]


def _held_by_another(
    view: ProjectView, path: Path, node: Node, state: DispatchState
) -> bool:
    """Whether the checkout is held in a way that leaves this step nothing to do.

    An ``AUTO_RESUME`` step's stopped run holds the checkout itself, so it is held
    against only by others.
    """
    holders = view.checkout_holders.get(path, frozenset[str]())
    if state is DispatchState.AUTO_RESUME:
        return bool(holders - {node.id})
    return bool(holders)


def _action(node: Node, facts: SliceDispatchFacts, view: ProjectView) -> Action | None:
    checkout = facts.checkout
    if not isinstance(checkout, Checkout):
        raise ValueError(f"step {node.id} has no resolved checkout")
    if facts.state is DispatchState.AUTO_RESUME:
        return _auto_resume(node, facts, view)
    if facts.state is DispatchState.READY and view.settings.pipeline is None:
        return None  # no pipeline configured: nothing to launch (D2)
    if facts.state in _LAUNCHES:
        # A launch or reissue goes ahead only on a passed pre-dispatch check (D5).
        check = view.dispatch_checks.get(node.id)
        if check is None:
            return None
        if isinstance(check, Block):
            return BlockDispatch(node.id, check)
        return _launch(node, facts, checkout, check, view.settings)
    raise ValueError(f"slice {node.id} in state {facts.state} is not planned")


def _launch(
    node: Node,
    facts: SliceDispatchFacts,
    checkout: Checkout,
    check: Ok,
    settings: ProjectSettings,
) -> LaunchRun:
    """The launch or reissue, with the evidence it was based on (D5)."""
    if facts.state is DispatchState.REISSUE:
        return _reissue(node, facts, check)
    if settings.pipeline is None:
        raise ValueError(f"slice {node.id} has no configured pipeline to launch")
    return LaunchRun(
        node.id,
        settings.pipeline,
        launch_params(settings, facts.slice_index),
        checkout.path,
        journal_extra={PARAM_DISPATCH_CHECK: dict(check.evidence)},
    )


def _auto_resume(
    node: Node, facts: SliceDispatchFacts, view: ProjectView
) -> Action | None:
    """Resume a run that stopped in a transient way, once ready and checked (D5)."""
    stopped = facts.continues
    if stopped is None:
        raise ValueError(f"step {node.id} is to be resumed but has no stopped run")
    document = recorded_document(stopped)
    if document is None or not resume_ready(document, view.now):
        return None
    check = view.dispatch_checks.get(node.id)
    if check is None:
        return None
    if isinstance(check, Block):
        return BlockDispatch(node.id, check)
    return ResumeRun(
        node.id,
        text_parameter(stopped, PARAM_RUN_ID),
        stopped.id,
        None,
        Path(text_parameter(stopped, PARAM_CHECKOUT)),
        cause=ResumeCause.TRANSIENT,
        journal_extra={PARAM_DISPATCH_CHECK: dict(check.evidence)},
    )


def _reissue(node: Node, facts: SliceDispatchFacts, check: Ok) -> LaunchRun:
    """The attempt that never started, repeated under its own run id (D9)."""
    old = facts.reissue_of
    if old is None:
        raise ValueError(f"step {node.id} is to be reissued but has no old entry")
    return LaunchRun(
        node.id,
        text_parameter(old, PARAM_PIPELINE),
        _params(old),
        Path(text_parameter(old, PARAM_CHECKOUT)),
        run_id=text_parameter(old, PARAM_RUN_ID),
        reissue_of=old.id,
        journal_extra={PARAM_DISPATCH_CHECK: dict(check.evidence)},
    )


def _params(entry: JournalEntry) -> Mapping[str, str]:
    value = entry.parameters.get(PARAM_PARAMS)
    if not isinstance(value, Mapping):
        raise ValueError(f"entry {entry.id} has unusable params: {value!r}")
    params: dict[str, str] = {}
    for key, item in cast("Mapping[object, object]", value).items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"entry {entry.id} has non-text params: {value!r}")
        params[key] = item
    return params
