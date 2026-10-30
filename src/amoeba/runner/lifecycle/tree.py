"""The lifecycle tree: a frozen, read-only view over one project's nodes (D1, D4).

Built from ``Store.nodes_for_project`` after reconcile. It does no I/O, so every
question Decide asks of the tree is a pure function of the node list.

A *linked* node is one CF reports: it has a CF index, and so does every ancestor.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from amoeba.runner.lifecycle.predecessors import slice_predecessor_done
from amoeba.store import BLOCKED_STATUSES, Node, NodeKind, NodeStatus

#: A linked node's identity within a project: its kind, CF project and CF index.
type NodeLinkKey = tuple[NodeKind, str, int]


class LifecycleTree:
    """A project's nodes, indexed by id, by link key, and by parent."""

    def __init__(self, nodes: Iterable[Node]) -> None:
        self._nodes: tuple[Node, ...] = tuple(nodes)
        self._by_id = {node.id: node for node in self._nodes}
        self._by_link: dict[NodeLinkKey, Node] = {}
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

    def node(self, node_id: str) -> Node | None:
        """The node with this id, or ``None`` when it is not in the tree."""
        return self._by_id.get(node_id)

    def children(self, node: Node) -> tuple[Node, ...]:
        """The node's direct children, in store order."""
        return self._children.get(node.id, ())

    def parent(self, node: Node) -> Node | None:
        """The node's parent, or ``None`` for a root or a parent not in the tree."""
        return None if node.parent_id is None else self._by_id.get(node.parent_id)

    def find_linked(self, kind: NodeKind, cf_project: str, index: int) -> Node | None:
        """The linked node of this kind, CF project and CF index, if any."""
        return self._by_link.get((kind, cf_project, index))

    def linked_nodes(self, cf_project: str) -> tuple[Node, ...]:
        """Every node of this CF project that carries a CF index, in store order."""
        return tuple(
            node
            for node in self._nodes
            if node.cf.project == cf_project and node.cf.index is not None
        )

    def linked_initiatives(self, cf_project: str) -> tuple[Node, ...]:
        """This CF project's initiatives that carry a CF index."""
        return tuple(
            node
            for node in self.linked_nodes(cf_project)
            if node.kind is NodeKind.INITIATIVE
        )

    def linked_slices(self, initiative: Node) -> tuple[Node, ...]:
        """The initiative's direct slice children that carry a CF index."""
        return tuple(
            child
            for child in self.children(initiative)
            if child.kind is NodeKind.SLICE and child.cf.index is not None
        )

    def is_linked(self, node: Node) -> bool:
        """Whether CF reports the node, and every ancestor of it.

        Every node needs its own CF index. A node whose parent is not in the tree is
        not linked.
        """
        current: Node | None = node
        while current is not None:
            if current.cf.index is None:
                return False
            if current.parent_id is None:
                return True
            current = self.parent(current)
        return False

    def ready_slices(self) -> Sequence[Node]:
        """The slice nodes that are ready to be worked, in store order (D1).

        A slice is ready when it is ``runnable``, linked, has no blocked ancestor
        and its predecessor slice is ``done``. A slice CF reports complete is
        marked ``done`` by reconcile, so it is not ``runnable`` here. Pure: it reads
        only this tree. This is the widest set; Decide narrows it by drive and hold,
        a free checkout and the pre-dispatch check.
        """
        return tuple(
            node
            for node in self._nodes
            if node.kind is NodeKind.SLICE
            and node.status is NodeStatus.RUNNABLE
            and self.is_linked(node)
            and not self._has_blocked_ancestor(node)
            and slice_predecessor_done(self, node)
        )

    def _has_blocked_ancestor(self, node: Node) -> bool:
        ancestor = self.parent(node)
        while ancestor is not None:
            if ancestor.status in BLOCKED_STATUSES:
                return True
            ancestor = self.parent(ancestor)
        return False


def link_key(node: Node) -> NodeLinkKey | None:
    """The node's link key, or ``None`` if it has no CF project or no index."""
    if node.cf.project is None or node.cf.index is None:
        return None
    return (node.kind, node.cf.project, node.cf.index)
