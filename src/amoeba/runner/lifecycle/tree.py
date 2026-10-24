"""The lifecycle tree: a frozen, read-only view over one project's nodes (D1, D4).

Built from ``Store.nodes_for_project`` after reconcile. It does no I/O, so every
question Decide asks of the tree is a pure function of the node list.

A *linked* node is one CF reports: it has a CF index, and so does every ancestor.
Step nodes carry no index of their own; they are linked through their parent.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store.models import Node, NodeKind

#: A linked node's identity within a project: its kind, CF project and CF index.
type LinkKey = tuple[NodeKind, str, int]


class LifecycleTree:
    """A project's nodes, indexed by id, by link key, and by parent."""

    def __init__(self, nodes: Iterable[Node]) -> None:
        self._nodes: tuple[Node, ...] = tuple(nodes)
        self._by_id = {node.id: node for node in self._nodes}
        self._by_link: dict[LinkKey, Node] = {}
        children: dict[str, list[Node]] = {}
        for node in self._nodes:
            key = link_key(node)
            if key is not None:
                self._by_link[key] = node
            if node.parent_id is not None:
                children.setdefault(node.parent_id, []).append(node)
        self._children = {parent: tuple(kids) for parent, kids in children.items()}

    @property
    def nodes(self) -> Sequence[Node]:
        """Every node, in the order the store returned them."""
        return self._nodes

    def children(self, node: Node) -> tuple[Node, ...]:
        """The node's direct children, in store order."""
        return self._children.get(node.id, ())

    def parent(self, node: Node) -> Node | None:
        """The node's parent, or ``None`` for a root or a parent not in the tree."""
        return None if node.parent_id is None else self._by_id.get(node.parent_id)

    def find_linked(self, kind: NodeKind, cf_project: str, index: int) -> Node | None:
        """The linked node of this kind, CF project and CF index, if any."""
        return self._by_link.get((kind, cf_project, index))

    def step_of(self, node: Node) -> LifecycleStep | None:
        """The node's step; ``None`` for a node that is not a step.

        Raises:
            ValueError: If a step node's ``cf.phase`` is absent or not a step.
        """
        if node.kind is not NodeKind.PHASE_OR_ARTIFACT:
            return None
        return LifecycleStep(node.cf.phase)

    def is_linked(self, node: Node) -> bool:
        """Whether CF reports the node, and every ancestor of it.

        A step node has no index; it is linked when its parent is. Any other node
        needs its own index. A node whose parent is not in the tree is not linked.
        """
        current: Node | None = node
        while current is not None:
            if current.kind is not NodeKind.PHASE_OR_ARTIFACT:
                if current.cf.index is None:
                    return False
            if current.parent_id is None:
                return True
            current = self.parent(current)
        return False


def link_key(node: Node) -> LinkKey | None:
    """The node's link key, or ``None`` if it has no CF project or no index."""
    if node.cf.project is None or node.cf.index is None:
        return None
    return (node.kind, node.cf.project, node.cf.index)
