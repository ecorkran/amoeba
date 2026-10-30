"""Reconcile one link's plan read into the node tree (D5, D6).

:func:`reconcile` applies a read in a fixed order, each rule checking the store
before it writes so a crash at any point is repaired by the next read:

1. orphan: unlink nodes CF no longer reports (``orphaning.py``);
2. create: initiative and slice nodes CF reports and the tree lacks (here);
3. block: slices whose CF status is unknown (``status_block.py``);
4. update: keep ``slice_name`` and ``artifact_path`` equal to CF's (``references.py``);
5. complete: mark slices CF shows complete, and initiatives whose slices are all
   done, as done (``completion.py``).

This module is the only caller of ``Store.create_node`` in ``src/amoeba``; a guard
test enforces it (D10). The read checks (``read_checks.py``) run first and decide
what each rule may touch, so a failed or partial read never orphans or creates.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from amoeba.runner.faults import TickFaults
from amoeba.runner.lifecycle.completion import (
    complete_initiatives,
    complete_observed_slices,
    complete_observed_steps,
)
from amoeba.runner.lifecycle.orphaning import orphan_unlisted
from amoeba.runner.lifecycle.plan_read import PlanRead, PlanReadFailed
from amoeba.runner.lifecycle.read_checks import ReadScope, checked_scope, observations
from amoeba.runner.lifecycle.references import update_references
from amoeba.runner.lifecycle.slugs import slice_name_from_design_file
from amoeba.runner.lifecycle.status_block import block_unknown_status
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import CFReference, Node, NodeKind, Store
from amoeba.upstream.context_forge import (
    CFInitiative,
    CFSliceEntry,
    CFSliceList,
    PlanEntryStatus,
)

logger = logging.getLogger(__name__)

#: Statuses CF uses to take a slice out of the plan; such a slice gets no node, so it
#: is never driven and never a predecessor (slice 132, D1).
_OUT_OF_PLAN_STATUSES = frozenset(
    {PlanEntryStatus.DEFERRED, PlanEntryStatus.DEPRECATED}
)


def reconcile(
    store: Store,
    project_id: str,
    cf_project_id: str,
    read: PlanRead | PlanReadFailed,
    faults: TickFaults,
) -> bool:
    """Apply one link's complete read to the node tree.

    Args:
        store: The project's store.
        project_id: The Amoeba project.
        cf_project_id: The linked CF project the read came from.
        read: A complete read, or the failure of one.
        faults: The tick's faults; the read checks add their ``plan_read_failed``
            faults here. Orphan and unknown-status blocks are direct store writes.

    Returns:
        Whether anything was written.
    """
    tree = _tree(store, project_id)
    scope = checked_scope(tree, cf_project_id, read)
    for fault in scope.faults:
        faults.add(fault)

    wrote = orphan_unlisted(store, tree, cf_project_id, read, scope)
    if not (isinstance(read, PlanRead) and scope.initiatives):
        return wrote
    # Each later rule sees the tree as the earlier ones left it; a read that
    # changes nothing builds the tree once.
    rules: tuple[Callable[[LifecycleTree], bool], ...] = (
        lambda t: _Creator(store, project_id, cf_project_id, t, read, scope).run(),
        lambda t: block_unknown_status(store, t, cf_project_id, read, scope),
        lambda t: update_references(store, t, cf_project_id, read, scope),
        lambda t: complete_observed_steps(
            store, t, project_id, cf_project_id, read, scope
        ),
        lambda t: complete_observed_slices(
            store, t, project_id, cf_project_id, read, scope
        ),
        lambda t: complete_initiatives(store, t, cf_project_id),
    )
    stale = wrote
    for rule in rules:
        if stale:
            tree = _tree(store, project_id)
        stale = rule(tree)
        wrote = wrote or stale
    return wrote


def _tree(store: Store, project_id: str) -> LifecycleTree:
    return LifecycleTree(store.nodes_for_project(project_id))


class _Creator:
    """The create rule: nodes and steps CF reports that the tree lacks."""

    def __init__(
        self,
        store: Store,
        project_id: str,
        cf_project_id: str,
        tree: LifecycleTree,
        read: PlanRead,
        scope: ReadScope,
    ) -> None:
        self._store = store
        self._project_id = project_id
        self._cf_project_id = cf_project_id
        self._tree = tree
        self._read = read
        self._scope = scope
        self._observations = observations(read, scope)
        self._wrote = False

    def run(self) -> bool:
        for initiative in self._read.initiatives:
            node = self._tree.find_linked(
                NodeKind.INITIATIVE, self._cf_project_id, initiative.index
            ) or self._create_initiative(initiative)
            slices = self._read.slices[initiative.index]
            if isinstance(slices, CFSliceList) and (
                initiative.index in self._scope.slice_initiatives
            ):
                for entry in slices.entries:
                    self._ensure_slice(node, entry)
        return self._wrote

    # -- initiatives -----------------------------------------------------------

    def _create_initiative(self, initiative: CFInitiative) -> Node:
        self._wrote = True
        return self._store.create_node(
            project_id=self._project_id,
            kind=NodeKind.INITIATIVE,
            title=initiative.name,
            cf=CFReference(
                project=self._cf_project_id,
                index=initiative.index,
                artifact_path=initiative.arch_file,
            ),
        )

    # -- slices ----------------------------------------------------------------

    def _ensure_slice(self, initiative_node: Node, entry: CFSliceEntry) -> None:
        linked = self._tree.find_linked(
            NodeKind.SLICE, self._cf_project_id, entry.index
        )
        if linked is None and entry.status not in _OUT_OF_PLAN_STATUSES:
            self._create_slice(initiative_node, entry)

    def _create_slice(self, initiative_node: Node, entry: CFSliceEntry) -> Node:
        self._wrote = True
        return self._store.create_node(
            project_id=self._project_id,
            kind=NodeKind.SLICE,
            title=entry.name,
            parent_id=initiative_node.id,
            cf=CFReference(
                project=self._cf_project_id,
                index=entry.index,
                slice_name=self._slice_name(entry),
                artifact_path=entry.design_file,
            ),
        )

    def _slice_name(self, entry: CFSliceEntry) -> str | None:
        name = slice_name_from_design_file(entry.design_file)
        if name is None and entry.design_file:
            logger.warning(
                "slice %s design file %r is not in the nnn-slice.{name}.md form; "
                "leaving slice_name unset",
                entry.index,
                entry.design_file,
            )
        return name
