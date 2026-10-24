"""Reconcile one link's plan read into the node tree (D5, D6).

:func:`reconcile` applies a read in a fixed order, each rule checking the store
before it writes so a crash at any point is repaired by the next read:

1. orphan: unlink nodes CF no longer reports (``orphaning.py``);
2. create: initiative, slice and step nodes CF reports and the tree lacks (here);
3. later rules, added by the tasks that follow, in this order.

This module is the only caller of ``Store.create_node`` in ``src/amoeba``; a guard
test enforces it (D10). The read checks (``read_checks.py``) run first and decide
what each rule may touch, so a failed or partial read never orphans or creates.
"""

from __future__ import annotations

import logging

from amoeba.runner.faults import TickFaults
from amoeba.runner.lifecycle.orphaning import orphan_unlisted
from amoeba.runner.lifecycle.plan_read import PlanRead, PlanReadFailed
from amoeba.runner.lifecycle.read_checks import ReadScope, checked_scope
from amoeba.runner.lifecycle.slugs import slice_name_from_design_file
from amoeba.runner.lifecycle.steps import (
    LifecycleStep,
    PlanObservation,
    StepLevel,
    step_complete,
    steps_at,
)
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import Store
from amoeba.store.models import CFReference, Node, NodeKind, NodeStatus
from amoeba.upstream.context_forge import (
    CFInitiative,
    CFSliceEntry,
    CFSliceList,
    PlanEntryStatus,
)

logger = logging.getLogger(__name__)

#: Statuses CF uses to take a slice out of the plan; such a slice gets no new steps.
_STEPLESS_STATUSES = frozenset({PlanEntryStatus.DEFERRED, PlanEntryStatus.DEPRECATED})


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
    if isinstance(read, PlanRead) and scope.initiatives:
        if wrote:
            tree = _tree(store, project_id)
        creator = _Creator(store, project_id, cf_project_id, tree, read, scope)
        wrote = creator.run() or wrote
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
        self._wrote = False

    def run(self) -> bool:
        for initiative in self._read.initiatives:
            node = self._tree.find_linked(
                NodeKind.INITIATIVE, self._cf_project_id, initiative.index
            ) or self._create_initiative(initiative)
            self._ensure_initiative_steps(node, initiative)
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

    def _ensure_initiative_steps(self, node: Node, initiative: CFInitiative) -> None:
        observation = PlanObservation(
            is_checked=initiative.is_checked,
            status=initiative.status,
            arch_file=initiative.arch_file,
            slice_list_read=initiative.index in self._scope.slice_initiatives,
        )
        self._ensure_steps(node, StepLevel.INITIATIVE, observation)

    # -- slices ----------------------------------------------------------------

    def _ensure_slice(self, initiative_node: Node, entry: CFSliceEntry) -> None:
        node = self._tree.find_linked(
            NodeKind.SLICE, self._cf_project_id, entry.index
        ) or self._create_slice(initiative_node, entry)
        if entry.status in _STEPLESS_STATUSES:
            return
        observation = PlanObservation(entry.is_checked, entry.status)
        self._ensure_steps(node, StepLevel.SLICE, observation)

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

    # -- steps -----------------------------------------------------------------

    def _ensure_steps(
        self, node: Node, level: StepLevel, observation: PlanObservation
    ) -> None:
        """Create the steps of ``level`` that ``node`` lacks, each with the status
        its completion predicate gives."""
        have = {self._tree.step_of(child) for child in self._tree.children(node)}
        for step in steps_at(level):
            if step not in have:
                self._create_step(node, step, observation)

    def _create_step(
        self, parent: Node, step: LifecycleStep, observation: PlanObservation
    ) -> None:
        self._wrote = True
        status = (
            NodeStatus.DONE if step_complete(step, observation) else NodeStatus.RUNNABLE
        )
        self._store.create_node(
            project_id=self._project_id,
            kind=NodeKind.PHASE_OR_ARTIFACT,
            title=step.value,
            parent_id=parent.id,
            status=status,
            cf=CFReference(project=self._cf_project_id, phase=step.value),
        )
