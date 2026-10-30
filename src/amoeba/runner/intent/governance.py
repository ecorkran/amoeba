"""What the PM's desired-state rows say about a step: driven, held, current (D4, D6).

Pure: no store access. The tick reads the rows once and builds a
``DesiredStateIndex``; everything here is a function of that index and the tree.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import DesiredState, Node

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
    """Whether the PM drives a step, and whether any pause holds it."""

    driven: bool
    held: bool


def _path_targets(tree: LifecycleTree, step: Node) -> list[Target]:
    """The targets whose rows govern ``step``, nearest first, ending at the project."""
    targets: list[Target] = []
    container = tree.parent(step)
    while container is not None:
        targets.append(container.id)
        container = tree.parent(container)
    targets.append(None)
    return targets


def governing(tree: LifecycleTree, index: DesiredStateIndex, step: Node) -> Governance:
    """Resolve drive (nearest row that sets it) and hold (any row) for ``step``.

    Raises:
        ValueError: If ``step`` is not a step node.
    """
    lifecycle_step = tree.step_of(step)
    if lifecycle_step is None:
        raise ValueError(f"node {step.id} is not a step")
    rows = [
        row
        for target in _path_targets(tree, step)
        if (row := index.row_for(target)) is not None
    ]
    driving = next((row for row in rows if row.drive is not None), None)
    driven = driving is not None and driving.drive is True
    return Governance(driven=driven, held=any(row.hold for row in rows))


def current_steps(tree: LifecycleTree, index: DesiredStateIndex) -> Sequence[Node]:
    """The ready steps that are driven and not held, in ``ready_steps`` order (D6)."""
    current: list[Node] = []
    for step in tree.ready_steps():
        governance = governing(tree, index, step)
        if governance.driven and not governance.held:
            current.append(step)
    return tuple(current)
