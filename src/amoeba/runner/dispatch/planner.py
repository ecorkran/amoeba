"""``DispatchPlanner``: point a checkout at a slice, then launch its pipeline (D3, D4).

Pure: it reads only the view's dispatch facts and held checkouts. For each current
pipeline step it proposes the one action its state calls for, and it proposes at most
one action per checkout per tick:

========================  =====================================================
state                     action
========================  =====================================================
``POINTED``               ``LaunchRun`` (the step already holds its checkout)
``REISSUE``               ``LaunchRun`` repeating the attempt that never started
``NEEDS_POINTER``         ``WriteSlicePointer``
``IN_FLIGHT``,
``AWAITING_ROUTING``      nothing
========================  =====================================================

A held checkout offers nothing to a step that is not ``POINTED``: a pointed step's
own claim is what holds its checkout. Within a free checkout, ``POINTED`` and
``REISSUE`` go before ``NEEDS_POINTER`` (a step that has written its pointer launches
before another writes over it), then by ``(initiative index, slice index, step
rank)``. A checkout the snapshot could not resolve gets nothing here: the tick blocks
the step (D1).
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
    WriteSlicePointer,
)
from amoeba.runner.dispatch.checkout import Checkout
from amoeba.runner.dispatch.facts import StepDispatchFacts
from amoeba.runner.dispatch.params import (
    PARAM_DISPATCH_CHECK,
    PARAM_MERGE_POLICY,
    PARAM_TARGET,
    dispatch_params,
    pipeline_for,
)
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.gates.predispatch import Block, Ok
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE, text_parameter
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.project_config import MergePolicy
from amoeba.runner.resolutions.vocabulary import ResolutionDecision
from amoeba.store import PARAM_CHECKOUT, PARAM_RUN_ID, JournalEntry, Node

#: The order states go in within a checkout: launches before pointer writes.
_RANK_LAUNCH = 0
_RANK_POINTER_WRITE = 1
_LAUNCHES = frozenset({DispatchState.POINTED, DispatchState.REISSUE})
_PRIORITY = {
    DispatchState.POINTED: _RANK_LAUNCH,
    DispatchState.REISSUE: _RANK_LAUNCH,
    DispatchState.NEEDS_POINTER: _RANK_POINTER_WRITE,
}


class DispatchPlanner:
    """Plans pointer writes and launches for the current pipeline steps."""

    def plan(self, view: ProjectView) -> Sequence[Action]:
        """At most one action per checkout, the best candidate in each."""
        best: dict[Path, tuple[tuple[int, tuple[int, int, int]], Node]] = {}
        for node in view.current_steps:
            facts = view.dispatch.get(node.id)
            if facts is None or not isinstance(facts.checkout, Checkout):
                continue
            if facts.state not in _PRIORITY:
                continue
            path = facts.checkout.path
            if (
                path in view.checkout_holders
                and facts.state is not DispatchState.POINTED
            ):
                continue
            rank = (_PRIORITY[facts.state], facts.sort_key)
            if path not in best or rank < best[path][0]:
                best[path] = (rank, node)
        ordered = sorted(best.values(), key=lambda pair: pair[0])
        actions = (_action(node, view.dispatch[node.id], view) for _, node in ordered)
        return [action for action in actions if action is not None]


def _action(node: Node, facts: StepDispatchFacts, view: ProjectView) -> Action | None:
    checkout = facts.checkout
    if not isinstance(checkout, Checkout):
        raise ValueError(f"step {node.id} has no resolved checkout")
    if facts.state in _LAUNCHES:
        # A launch or reissue goes ahead only on a passed pre-dispatch check (D5).
        check = view.dispatch_checks.get(node.id)
        if check is None:
            return None
        if isinstance(check, Block):
            return BlockDispatch(node.id, check)
        return _launch(node, facts, checkout, check, view.merge_policy)
    match facts.state:
        case DispatchState.NEEDS_POINTER:
            return WriteSlicePointer(
                node.id,
                facts.cf_project_id,
                facts.slice_index,
                checkout,
                _carried_resolution(facts),
            )
        case _:
            raise ValueError(f"step {node.id} in state {facts.state} is not planned")


def _launch(
    node: Node,
    facts: StepDispatchFacts,
    checkout: Checkout,
    check: Ok,
    policy: MergePolicy,
) -> LaunchRun:
    """The launch or reissue, with the evidence it was based on (D5, D8)."""
    if facts.state is DispatchState.REISSUE:
        return _reissue(node, facts, check)
    extra: dict[str, object] = {PARAM_DISPATCH_CHECK: dict(check.evidence)}
    if facts.step is LifecycleStep.IMPLEMENTATION:
        extra[PARAM_MERGE_POLICY] = policy.value
        extra[PARAM_TARGET] = check.evidence["target"]
    return LaunchRun(
        node.id,
        pipeline_for(facts.step),
        dispatch_params(facts.step, facts.slice_index, policy),
        checkout.path,
        journal_extra=extra,
    )


def _carried_resolution(facts: StepDispatchFacts) -> str | None:
    """The blocked state id of the ``rerun`` this pointer write carries out."""
    blocked = facts.resolution
    if blocked is None or blocked.resolution is None:
        return None
    rerun = blocked.resolution.decision == ResolutionDecision.RERUN.value
    return blocked.id if rerun else None


def _reissue(node: Node, facts: StepDispatchFacts, check: Ok) -> LaunchRun:
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
        journal_extra=_reissue_extra(old, check),
    )


def _reissue_extra(old: JournalEntry, check: Ok) -> Mapping[str, object]:
    """A run keeps the policy and target it was first launched under (D8)."""
    kept = {
        key: old.parameters[key]
        for key in (PARAM_MERGE_POLICY, PARAM_TARGET)
        if key in old.parameters
    }
    return {**kept, PARAM_DISPATCH_CHECK: dict(check.evidence)}


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
