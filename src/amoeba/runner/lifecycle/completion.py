"""The complete rules: mark a slice or initiative done when CF's plan shows it so (D1).

* a linked slice CF reports complete, that is ``runnable`` with no unresolved journal
  entry, becomes ``done`` (work the PM did by hand);
* an initiative whose linked slices are all ``done`` becomes ``done``.

Anything else is left alone. A run in flight, a blocked slice and a slice with an
unresolved journal entry finish their own course, and the store refuses ``done``
while an entry is unresolved.
"""

from __future__ import annotations

from amoeba.runner.lifecycle.plan_read import PlanRead
from amoeba.runner.lifecycle.read_checks import (
    ObservationKey,
    PlanObservation,
    ReadScope,
    observations,
)
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import Node, NodeKind, NodeStatus, Store
from amoeba.upstream.context_forge import reported_complete


def _observation_for(
    observations: dict[ObservationKey, PlanObservation], owner: Node
) -> PlanObservation | None:
    if owner.cf.index is None:
        return None
    return observations.get((owner.kind, owner.cf.index))


def complete_observed_slices(
    store: Store,
    tree: LifecycleTree,
    project_id: str,
    cf_project_id: str,
    read: PlanRead,
    scope: ReadScope,
) -> bool:
    """Mark done every linked slice CF reports complete (work the PM did by hand).

    A slice with an unresolved journal entry, or one that is blocked, is left
    alone: its run finishes its own course. Returns whether anything was written.
    """
    found = observations(read, scope)
    has_open_entry = {
        entry.node_id for entry in store.unresolved_journal_entries(project_id)
    }
    wrote = False
    for node in tree.nodes:
        if node.kind is not NodeKind.SLICE or node.cf.project != cf_project_id:
            continue
        observation = _observation_for(found, node)
        if observation is None or not tree.is_linked(node):
            continue
        if (
            reported_complete(observation)
            and node.status is NodeStatus.RUNNABLE
            and node.id not in has_open_entry
        ):
            store.update_node_status(node.id, NodeStatus.DONE)
            wrote = True
    return wrote


def complete_initiatives(store: Store, tree: LifecycleTree, cf_project_id: str) -> bool:
    """Mark an initiative done when every slice under it is done (D1).

    An initiative with no linked slice is not done: there is nothing to have
    finished. Returns whether anything was written.
    """
    wrote = False
    for initiative in tree.linked_initiatives(cf_project_id):
        slices = tree.linked_slices(initiative)
        if (
            slices
            and initiative.status is NodeStatus.RUNNABLE
            and all(child.status is NodeStatus.DONE for child in slices)
        ):
            store.update_node_status(initiative.id, NodeStatus.DONE)
            wrote = True
    return wrote
