"""What each lifecycle step waits for (D4): the one place that says so.

A step is ready when its predecessors are ``done``. Adding a cross-project edge
(slice 180) widens the view this function reads, not its callers.

Import direction: ``tree.py`` imports this module (for ``ready_steps``), so this
module names ``LifecycleTree`` only under ``TYPE_CHECKING`` and uses the tree
through its methods.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import Node, NodeKind, NodeStatus

if TYPE_CHECKING:
    from amoeba.runner.lifecycle.tree import LifecycleTree


def predecessors(tree: LifecycleTree, node: Node) -> tuple[Node, ...]:
    """The step nodes ``node`` waits for, those that exist.

    Raises:
        ValueError: If ``node`` is not a step node.
    """
    return tuple(found for found in _waits_for(tree, node) if found is not None)


def predecessors_done(tree: LifecycleTree, node: Node) -> bool:
    """Whether every predecessor exists and is ``done``.

    A predecessor step that does not exist yet (reconcile creates missing steps)
    is not done, so the step waits for it.

    Raises:
        ValueError: If ``node`` is not a step node.
    """
    return all(
        found is not None and found.status is NodeStatus.DONE
        for found in _waits_for(tree, node)
    )


def _waits_for(tree: LifecycleTree, node: Node) -> tuple[Node | None, ...]:
    """D4's table, one rule per step; ``None`` marks a required step not created."""
    step = tree.step_of(node)
    owner = tree.parent(node)
    if step is None or owner is None:
        raise ValueError(f"node {node.id} is not a step with a parent")

    match step:
        case LifecycleStep.ARCHITECTURE:
            return ()
        case LifecycleStep.SLICE_PLAN:
            return (_step_of(tree, owner, LifecycleStep.ARCHITECTURE),)
        case LifecycleStep.SLICE_DESIGN:
            initiative = _parent_or_fail(tree, owner)
            return (_step_of(tree, initiative, LifecycleStep.SLICE_PLAN),)
        case LifecycleStep.TASKS:
            return (_step_of(tree, owner, LifecycleStep.SLICE_DESIGN),)
        case LifecycleStep.IMPLEMENTATION:
            previous = _previous_eligible_slice(tree, owner)
            earlier_merge = (
                ()
                if previous is None
                else (_step_of(tree, previous, LifecycleStep.MERGE),)
            )
            return (_step_of(tree, owner, LifecycleStep.TASKS), *earlier_merge)
        case LifecycleStep.MERGE:
            return (_step_of(tree, owner, LifecycleStep.IMPLEMENTATION),)
        case LifecycleStep.INTEGRATION:
            merges = tuple(
                _step_of(tree, eligible, LifecycleStep.MERGE)
                for eligible in _eligible_slices(tree, owner)
            )
            return (_step_of(tree, owner, LifecycleStep.SLICE_PLAN), *merges)


def _step_of(tree: LifecycleTree, owner: Node, step: LifecycleStep) -> Node | None:
    """The ``step`` child of ``owner``, if it exists."""
    for child in tree.children(owner):
        if tree.step_of(child) is step:
            return child
    return None


def _parent_or_fail(tree: LifecycleTree, node: Node) -> Node:
    parent = tree.parent(node)
    if parent is None:
        raise ValueError(f"node {node.id} has no parent in the tree")
    return parent


def _eligible_slices(tree: LifecycleTree, initiative: Node) -> tuple[Node, ...]:
    """Linked slices that have step children, by ascending CF index.

    A ``deferred`` or ``deprecated`` slice has no steps (D6), so it is skipped; an
    orphan has no index, so it is too. A slice with an unknown status has steps
    and stays in the order.
    """
    indexed = [
        (child.cf.index, child)
        for child in tree.children(initiative)
        if child.kind is NodeKind.SLICE
        and child.cf.index is not None
        and any(tree.step_of(grandchild) for grandchild in tree.children(child))
    ]
    return tuple(child for _, child in sorted(indexed, key=lambda pair: pair[0]))


def _previous_eligible_slice(tree: LifecycleTree, slice_node: Node) -> Node | None:
    """The eligible slice with the next lower index in the same initiative."""
    index = slice_node.cf.index
    if index is None:
        return None
    initiative = _parent_or_fail(tree, slice_node)
    lower = [
        candidate
        for candidate in _eligible_slices(tree, initiative)
        if candidate.cf.index is not None and candidate.cf.index < index
    ]
    return lower[-1] if lower else None
