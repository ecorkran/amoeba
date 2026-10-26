"""The resolution stage: answer every pending PM resolution (slice 127, D3).

Store reads and pure computations, then one ``acknowledge_resolution`` per
resolution, which lands the answer and its effect in one transaction. There is no
``except`` here: a store failure and any other exception propagate to the tick and
the tenant (122's boundary), leaving the resolution flagged for the next tick.
"""

from __future__ import annotations

from amoeba.runner.faults import NodeContext
from amoeba.runner.lifecycle.steps import STEP_MAP, Executor
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.runner.resolutions.classify import classify
from amoeba.runner.resolutions.judge import checkpoint_of, judge_resolution
from amoeba.store import (
    BlockedState,
    Store,
    latest_run_entry,
)


def apply_pending_resolutions(
    store: Store, project_id: str, tree: LifecycleTree, context: NodeContext
) -> bool:
    """Answer each pending resolution of the project, oldest first.

    Returns:
        Whether anything was acknowledged.
    """
    answered = False
    for blocked in store.pending_resolutions(project_id):
        # So 122's catch blocks the node whose resolution failed to be answered.
        context.set(blocked.node_id)
        _answer(store, project_id, tree, blocked)
        answered = True
    return answered


def _answer(
    store: Store, project_id: str, tree: LifecycleTree, blocked: BlockedState
) -> None:
    entries = store.journal_entries(project_id, node_id=blocked.node_id)
    situation = classify(_executor_of(tree, blocked), entries)
    answer = judge_resolution(
        blocked, situation, checkpoint_of(latest_run_entry(entries))
    )
    store.acknowledge_resolution(
        blocked.id,
        outcome=answer.outcome,
        code=answer.code,
        reason=answer.reason,
        effect=answer.effect,
    )


def _executor_of(tree: LifecycleTree, blocked: BlockedState) -> Executor | None:
    """Who does the blocked node's step; ``None`` when it is not a step."""
    node = tree.node(blocked.node_id)
    if node is None:
        raise ValueError(f"blocked state {blocked.id} names a node not in the tree")
    step = tree.step_of(node)
    return None if step is None else STEP_MAP[step].executor
