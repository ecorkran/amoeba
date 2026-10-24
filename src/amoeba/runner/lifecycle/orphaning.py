"""The orphan rule: unlink nodes CF no longer reports (D5 step 1).

A linked node is orphaned when CF stopped reporting it:

* an initiative missing from a successful initiatives read;
* a slice missing from every successful slice read, when its own initiative's
  slice list was read successfully; or
* a slice listed under a different initiative from its parent (a move, handled like
  a renumber: the old node is orphaned and the create rule makes a new one).

Orphaning clears ``cf.index`` and ``cf.slice_name``, so a renumbered slice's new node
and its orphan can never both match one review, and so the unique link index never
sees two linked nodes. A node that is neither blocked nor done is blocked on a
human; a ``done`` node is just unlinked; an already-blocked node keeps its open
escalation. Nothing is deleted, and descendants are not touched: ``is_linked`` is
false for anything under an unlinked ancestor.

The block is written *before* the unlink, so a crash between the two leaves a node
that is blocked and still linked, which the next read finishes. The other order
would leave an unlinked node nobody could find again.
"""

from __future__ import annotations

import logging

from amoeba.runner.faults import (
    PAYLOAD_CF_PROJECT_ID,
    PAYLOAD_FAULT_KIND,
    PAYLOAD_FORMER_INDEX,
    PAYLOAD_FORMER_SLICE_NAME,
    FaultKind,
)
from amoeba.runner.lifecycle.plan_read import PlanRead, PlanReadFailed
from amoeba.runner.lifecycle.read_checks import ReadScope
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import (
    BLOCKED_STATUSES,
    BlockedKind,
    CFReference,
    Node,
    NodeKind,
    NodeStatus,
    Store,
)
from amoeba.upstream.context_forge import CFSliceList

logger = logging.getLogger(__name__)


def orphan_unlisted(
    store: Store,
    tree: LifecycleTree,
    cf_project_id: str,
    read: PlanRead | PlanReadFailed,
    scope: ReadScope,
) -> bool:
    """Orphan every linked node the in-scope parts of ``read`` no longer report.

    Returns:
        Whether anything was written.
    """
    if not scope.initiatives or isinstance(read, PlanReadFailed):
        return False
    listed_initiatives = {initiative.index for initiative in read.initiatives}
    listed_slices = _slices_by_initiative(read, scope)

    orphans = [
        node
        for node in tree.linked_nodes(cf_project_id)
        if _is_unlisted(tree, node, listed_initiatives, listed_slices)
    ]
    for node in orphans:
        _orphan(store, node, cf_project_id)
    return bool(orphans)


def _slices_by_initiative(read: PlanRead, scope: ReadScope) -> dict[int, set[int]]:
    """Each in-scope initiative index to the slice indexes it lists."""
    listed: dict[int, set[int]] = {}
    for initiative_index in scope.slice_initiatives:
        got = read.slices[initiative_index]
        if isinstance(got, CFSliceList):
            listed[initiative_index] = {entry.index for entry in got.entries}
    return listed


def _is_unlisted(
    tree: LifecycleTree,
    node: Node,
    listed_initiatives: set[int],
    listed_slices: dict[int, set[int]],
) -> bool:
    if node.kind is NodeKind.INITIATIVE:
        return node.cf.index not in listed_initiatives
    if node.kind is not NodeKind.SLICE:
        return False
    owners = [i for i, indexes in listed_slices.items() if node.cf.index in indexes]
    parent = tree.parent(node)
    parent_index = None if parent is None else parent.cf.index
    if owners:
        # Listed somewhere: fine under its own parent, a move anywhere else.
        return parent_index not in owners
    # Missing from every read: orphaned only when its own initiative was read.
    return parent_index in listed_slices


def _orphan(store: Store, node: Node, cf_project_id: str) -> None:
    former_index = node.cf.index
    if node.status is NodeStatus.DONE:
        logger.info(
            "unlinking done node %s: CF no longer reports index %s",
            node.id,
            former_index,
        )
    elif node.status in BLOCKED_STATUSES:
        logger.warning(
            "orphaned node %s is already blocked; keeping its escalation "
            "(former index %s)",
            node.id,
            former_index,
        )
    else:
        store.block(
            node.id,
            kind=BlockedKind.HUMAN,
            context=f"orphaned: CF no longer reports index {former_index}",
            payload={
                PAYLOAD_FAULT_KIND: FaultKind.LIFECYCLE_ORPHAN.value,
                PAYLOAD_CF_PROJECT_ID: cf_project_id,
                PAYLOAD_FORMER_INDEX: former_index,
                PAYLOAD_FORMER_SLICE_NAME: node.cf.slice_name,
            },
        )
    store.update_cf_reference(
        node.id,
        CFReference(
            project=node.cf.project,
            phase=node.cf.phase,
            slice_name=None,
            artifact_path=node.cf.artifact_path,
            index=None,
        ),
    )
