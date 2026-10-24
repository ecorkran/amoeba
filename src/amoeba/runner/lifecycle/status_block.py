"""The unknown-status block (D6): a slice CF reports in a state the Runner cannot read.

``degraded``, or a value outside :class:`PlanEntryStatus`, is never read as a default
("unknown escalates"). The slice keeps its steps (the create rule makes them) and is
blocked on a human. This is a node fault, not ``plan_read_failed``: the read
succeeded, and the problem belongs to one slice.

The rule runs on every read, not only at creation: a block the PM resolved while the
status is still unknown is restored on the next read. While the slice is blocked its
steps are not ready, and its ``merge`` is not done, so later slices'
``implementation`` waits.
"""

from __future__ import annotations

import logging

from amoeba.runner.faults import (
    PAYLOAD_FAULT_KIND,
    PAYLOAD_INDEX,
    PAYLOAD_STATUS,
    FaultKind,
)
from amoeba.runner.lifecycle.plan_read import PlanRead
from amoeba.runner.lifecycle.read_checks import ReadScope
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import Store
from amoeba.store.models import (
    BLOCKED_STATUSES,
    BlockedKind,
    Node,
    NodeKind,
    NodeStatus,
)
from amoeba.upstream.context_forge import (
    CFSliceEntry,
    CFSliceList,
    PlanEntryStatus,
    UnknownPlanStatus,
)

logger = logging.getLogger(__name__)


def block_unknown_status(
    store: Store,
    tree: LifecycleTree,
    cf_project_id: str,
    read: PlanRead,
    scope: ReadScope,
) -> bool:
    """Block each linked slice whose CF status is unknown and that is not already
    blocked or done.

    Returns:
        Whether anything was written.
    """
    wrote = False
    for initiative_index in sorted(scope.slice_initiatives):
        slices = read.slices[initiative_index]
        if not isinstance(slices, CFSliceList):
            continue
        for entry in slices.entries:
            raw = _unknown_status_text(entry)
            node = tree.find_linked(NodeKind.SLICE, cf_project_id, entry.index)
            if raw is None or node is None:
                continue
            if node.status is NodeStatus.DONE or node.status in BLOCKED_STATUSES:
                continue
            _block(store, node, entry.index, raw)
            wrote = True
    return wrote


def _block(store: Store, node: Node, index: int, raw: str) -> None:
    store.block(
        node.id,
        kind=BlockedKind.HUMAN,
        context=f"plan status unknown: CF reports {raw!r} for index {index}",
        payload={
            PAYLOAD_FAULT_KIND: FaultKind.PLAN_STATUS_UNKNOWN.value,
            PAYLOAD_INDEX: index,
            PAYLOAD_STATUS: raw,
        },
    )
    logger.warning(
        "slice %s (index %s) blocked: unknown CF status %r", node.id, index, raw
    )


def _unknown_status_text(entry: CFSliceEntry) -> str | None:
    """The status text when it is unknown (``degraded`` or out of vocabulary)."""
    status = entry.status
    if isinstance(status, UnknownPlanStatus):
        return status.raw
    if status is PlanEntryStatus.DEGRADED:
        return status.value
    return None
