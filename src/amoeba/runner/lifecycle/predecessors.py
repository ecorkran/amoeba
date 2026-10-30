"""What a slice waits for (D1): the one place that says so.

A slice is ready when its predecessor slice is ``done``. Adding a cross-project edge
(slice 180) widens the view this function reads, not its callers.

``tree.py`` imports this module, so this module names ``LifecycleTree`` only under
``TYPE_CHECKING`` and uses the tree through its methods.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from amoeba.store import Node, NodeStatus

if TYPE_CHECKING:
    from amoeba.runner.lifecycle.tree import LifecycleTree


def linked_slices_by_index(tree: LifecycleTree, initiative: Node) -> tuple[Node, ...]:
    """The initiative's linked slices by ascending CF index.

    A slice CF lists under a ``deferred`` or ``deprecated`` status has no node, and
    an orphan has no index, so neither is here.
    """
    return tuple(
        sorted(tree.linked_slices(initiative), key=lambda node: node.cf.index or 0)
    )


def slice_predecessor(tree: LifecycleTree, slice_node: Node) -> Node | None:
    """The linked slice with the next lower CF index in the same initiative.

    This is the one place that says what a slice waits for. 180 widens it with
    cross-project edges, not its callers.
    """
    index = slice_node.cf.index
    initiative = tree.parent(slice_node)
    if index is None or initiative is None:
        return None
    lower = [
        candidate
        for candidate in linked_slices_by_index(tree, initiative)
        if candidate.cf.index is not None and candidate.cf.index < index
    ]
    return lower[-1] if lower else None


def slice_predecessor_done(tree: LifecycleTree, slice_node: Node) -> bool:
    """Whether the slice has no predecessor, or its predecessor is ``done``."""
    previous = slice_predecessor(tree, slice_node)
    return previous is None or previous.status is NodeStatus.DONE
