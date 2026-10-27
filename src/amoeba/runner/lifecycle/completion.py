"""The complete rule: mark a step done when CF's plan shows it complete (D5 step 4).

For each linked step whose completion predicate (D3) holds:

* ``runnable`` with no unresolved journal entry becomes ``done``;
* ``blocked_on_human`` with a human executor is resolved by ``runner`` and then
  marked ``done``: the person did the work and CF shows it;
* anything else is left alone. A run in flight, a blocked pipeline step and a step
  with an unresolved journal entry finish their own course, and the store refuses
  ``done`` while an entry is unresolved.

A crash between the resolve and the status write leaves a runnable step, which the
first case finishes on the next read, so the rule needs no extra repair.
"""

from __future__ import annotations

from amoeba.runner.faults import RUNNER_ACTOR
from amoeba.runner.lifecycle.plan_read import PlanRead
from amoeba.runner.lifecycle.read_checks import (
    ObservationKey,
    ReadScope,
    observations,
)
from amoeba.runner.lifecycle.steps import (
    STEP_MAP,
    Executor,
    LifecycleStep,
    PlanObservation,
    step_complete,
)
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import Node, NodeStatus, Store


def complete_observed_steps(
    store: Store,
    tree: LifecycleTree,
    project_id: str,
    cf_project_id: str,
    read: PlanRead,
    scope: ReadScope,
) -> bool:
    """Mark done every linked step the in-scope read shows complete.

    Returns:
        Whether anything was written.
    """
    found = observations(read, scope)
    has_open_entry = {
        entry.node_id for entry in store.unresolved_journal_entries(project_id)
    }
    wrote = False
    for node in tree.nodes:
        step = tree.step_of(node)
        owner = tree.parent(node)
        if step is None or owner is None or owner.cf.project != cf_project_id:
            continue
        observation = _observation_for(found, owner)
        if observation is None or not tree.is_linked(node):
            continue
        if step_complete(step, observation):
            detail = f"observed: {step} is complete in the CF plan"
            wrote = (
                complete_step(store, node, step, has_open_entry, detail=detail) or wrote
            )
    return wrote


def _observation_for(
    observations: dict[ObservationKey, PlanObservation], owner: Node
) -> PlanObservation | None:
    if owner.cf.index is None:
        return None
    return observations.get((owner.kind, owner.cf.index))


def complete_step(
    store: Store,
    node: Node,
    step: LifecycleStep,
    has_open_entry: set[str],
    *,
    detail: str,
) -> bool:
    """Mark ``node`` done, resolving a human step's block first; ``detail`` says why.

    Used by the plan read (CF shows the step complete) and by the merge observation
    (git shows the head merged). Returns whether anything was written.
    """
    if node.id in has_open_entry:
        return False
    if node.status is NodeStatus.RUNNABLE:
        store.update_node_status(node.id, NodeStatus.DONE)
        return True
    if node.status is NodeStatus.BLOCKED_ON_HUMAN and (
        STEP_MAP[step].executor is Executor.HUMAN
    ):
        store.resolve(
            node.id,
            resolved_by=RUNNER_ACTOR,
            detail=detail,
        )
        store.update_node_status(node.id, NodeStatus.DONE)
        return True
    return False
