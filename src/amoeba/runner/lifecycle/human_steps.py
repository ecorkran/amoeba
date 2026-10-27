"""Human steps: a ready step a person does is blocked on a person (D9).

A human step is ``blocked_on_human`` from the moment it becomes current, where
current means ready and, from slice 124, driven. :class:`HumanStepPlanner` asks for
that; :func:`block_human_step` applies it as one store write.

Why a planner and not reconcile: reconcile only projects what CF says. Putting a
person on a step is a decision about the next action, and drive (124) has to filter
it like any dispatch. The planner is in the production tuple and plans only over
current steps, so linking a project blocks nothing until the PM drives it.

If a person resolves the block without doing the work, the step is runnable again,
and while it is still current it is blocked again on the next tick: the intended
"still waiting on you". When the work is done, the complete rule resolves the block
and marks the step done.
"""

from __future__ import annotations

from collections.abc import Sequence

from amoeba.runner.decide import Action, BlockHumanStep, ProjectView
from amoeba.runner.faults import (
    PAYLOAD_CF_PROJECT_ID,
    PAYLOAD_INDEX,
    PAYLOAD_STEP,
)
from amoeba.runner.gates.merge_observation import NotMerged, Unobservable
from amoeba.runner.lifecycle.steps import STEP_MAP, Executor, LifecycleStep
from amoeba.store import BlockedKind, Store

#: Block payload keys for a merge step that cannot be observed (slice 128, D9).
PAYLOAD_MERGE_OBSERVATION = "merge_observation"
PAYLOAD_REASON = "reason"


class HumanStepPlanner:
    """Blocks each current step whose executor is a person.

    Current means ready, driven and not held (124): a project the PM has not driven
    is never blocked on.
    """

    def plan(self, view: ProjectView) -> Sequence[Action]:
        actions: list[Action] = []
        for node in view.current_steps:
            step = view.tree.step_of(node)
            if step is None or STEP_MAP[step].executor is not Executor.HUMAN:
                continue
            if step is LifecycleStep.MERGE:
                action = _merge_action(node.id, view)
                if action is not None:
                    actions.append(action)
                continue
            actions.append(BlockHumanStep(node.id))
        return actions


def _merge_action(node_id: str, view: ProjectView) -> BlockHumanStep | None:
    """A merge step waits on a person only while git shows it is not merged (D9).

    No observation this tick (a read failed or was cut off) blocks nothing: it would
    otherwise block a step that ``auto`` already merged.
    """
    observation = view.merge_observations.get(node_id)
    if isinstance(observation, NotMerged):
        return BlockHumanStep(node_id)
    if isinstance(observation, Unobservable):
        return BlockHumanStep(
            node_id,
            {
                PAYLOAD_MERGE_OBSERVATION: "unobservable",
                PAYLOAD_REASON: observation.reason,
            },
        )
    return None


def block_human_step(store: Store, action: BlockHumanStep) -> None:
    """Block the step on a human, with the step and its owner's CF index named."""
    node = store.get_node(action.node_id)
    owner = (
        None
        if node is None or node.parent_id is None
        else store.get_node(node.parent_id)
    )
    if node is None or owner is None:
        raise ValueError(f"human step {action.node_id} or its owner is missing")
    step = LifecycleStep(node.cf.phase)
    store.block(
        node.id,
        kind=BlockedKind.HUMAN,
        context=f"{step.value} is a human step",
        payload={
            PAYLOAD_STEP: step.value,
            PAYLOAD_CF_PROJECT_ID: node.cf.project,
            PAYLOAD_INDEX: owner.cf.index,
            **action.payload_extra,
        },
    )
