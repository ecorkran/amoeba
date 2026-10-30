"""What the PM's desired-state rows say about a slice: driven, held, current (D4, D6).

Pure: no store access. The tick reads the rows once and builds a
``DesiredStateIndex``; everything here is a function of that index and the tree.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import DesiredState, Node, NodeKind

#: The index key of the project-level row.
type Target = str | None


class DesiredStateIndex:
    """A project's desired-state rows, by target (``None`` is the project)."""

    def __init__(self, rows: Iterable[DesiredState]) -> None:
        self._by_target: dict[Target, DesiredState] = {row.node_id: row for row in rows}

    def row_for(self, target: Target) -> DesiredState | None:
        """The row at ``target``, or ``None``."""
        return self._by_target.get(target)

    def drives_anything(self) -> bool:
        """Whether any row drives. Observe scoping reads this (slices 125, 128)."""
        return any(row.drive is True for row in self._by_target.values())


@dataclass(frozen=True)
class Governance:
    """Whether the PM drives a slice, and whether any pause holds it."""

    driven: bool
    held: bool


def _path_targets(tree: LifecycleTree, slice_node: Node) -> list[Target]:
    """The targets whose rows govern a slice: itself, its initiative, the project."""
    targets: list[Target] = [slice_node.id]
    container = tree.parent(slice_node)
    while container is not None:
        targets.append(container.id)
        container = tree.parent(container)
    targets.append(None)
    return targets


def governing(
    tree: LifecycleTree, index: DesiredStateIndex, slice_node: Node
) -> Governance:
    """Resolve drive (nearest row that sets it) and hold (any row) for a slice.

    Raises:
        ValueError: If ``slice_node`` is not a slice node.
    """
    if slice_node.kind is not NodeKind.SLICE:
        raise ValueError(f"node {slice_node.id} is not a slice")
    rows = [
        row
        for target in _path_targets(tree, slice_node)
        if (row := index.row_for(target)) is not None
    ]
    driving = next((row for row in rows if row.drive is not None), None)
    driven = driving is not None and driving.drive is True
    return Governance(driven=driven, held=any(row.hold for row in rows))


def current_slices(tree: LifecycleTree, index: DesiredStateIndex) -> Sequence[Node]:
    """The ready slices that are driven and not held, in ``ready_slices`` order."""
    current: list[Node] = []
    for slice_node in tree.ready_slices():
        governance = governing(tree, index, slice_node)
        if governance.driven and not governance.held:
            current.append(slice_node)
    return tuple(current)
