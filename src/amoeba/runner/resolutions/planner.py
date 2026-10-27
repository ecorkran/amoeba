"""``ContinuationPlanner``: resume or observe the run an applied resolution names.

Pure, like ``DispatchPlanner``: it reads only the view's dispatch facts and checkout
holders. For each current pipeline step in ``RESUME`` or ``REOBSERVE`` it proposes
one action. It acts when the run's checkout is held by no one or only by the step
itself, because the paused run it continues is that step's own; any other holder
makes it wait, like any launch (slice 127, D5). The two planners never act on the
same step, since a step is in one dispatch state.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from amoeba.runner.decide import (
    Action,
    BlockDispatch,
    ObserveRun,
    ProjectView,
    ResumeRun,
)
from amoeba.runner.dispatch.checkout import Checkout
from amoeba.runner.dispatch.facts import StepDispatchFacts
from amoeba.runner.dispatch.params import PARAM_DISPATCH_CHECK
from amoeba.runner.dispatch.state import DispatchState
from amoeba.runner.gates.predispatch import Block
from amoeba.runner.launch import text_parameter
from amoeba.runner.resolutions.vocabulary import Continuation
from amoeba.store import PARAM_CHECKOUT, PARAM_RUN_ID, Node


class ContinuationPlanner:
    """Plans resumes and observations for the current steps a PM resolved."""

    def plan(self, view: ProjectView) -> Sequence[Action]:
        """One action per eligible step, in the view's step order."""
        actions: list[Action] = []
        for node in view.current_steps:
            facts = view.dispatch.get(node.id)
            if facts is None or facts.state not in _STATES:
                continue
            action = _action(node, facts, view)
            if action is not None:
                actions.append(action)
        return actions


_STATES = frozenset({DispatchState.RESUME, DispatchState.REOBSERVE})


def _action(node: Node, facts: StepDispatchFacts, view: ProjectView) -> Action | None:
    """The step's action, or ``None`` while it waits or cannot be placed."""
    continued, resolution = facts.continues, facts.resolution
    if not isinstance(facts.checkout, Checkout):
        return None
    if continued is None or resolution is None or resolution.resolution is None:
        raise ValueError(
            f"step {node.id} is {facts.state} without its entry or decision"
        )
    checkout = Path(text_parameter(continued, PARAM_CHECKOUT))
    if view.checkout_holders.get(checkout, frozenset()) - {node.id}:
        return None
    run_id = text_parameter(continued, PARAM_RUN_ID)
    if facts.state is DispatchState.REOBSERVE:
        return ObserveRun(node.id, run_id, continued.id, resolution.id, checkout)
    # A resume goes ahead only on a passed pre-dispatch check (slice 128, D5).
    check = view.dispatch_checks.get(node.id)
    if check is None:
        return None
    if isinstance(check, Block):
        return BlockDispatch(node.id, check)
    decision = Continuation(resolution.resolution.decision)
    return ResumeRun(
        node.id,
        run_id,
        decision,
        continued.id,
        resolution.id,
        checkout,
        journal_extra={PARAM_DISPATCH_CHECK: dict(check.evidence)},
    )
