"""Node writes and reads.

Mixed into ``Store``; see ``store.py`` for the assembled public class. Every
write is transactional and raises on failure — no method here returns a status
code a caller can ignore.
"""

from __future__ import annotations

from amoeba.store import sql
from amoeba.store._base import isoformat, new_id, now
from amoeba.store._block_writer import BlockWriter, refuse_blocked_status
from amoeba.store.mapping import map_node
from amoeba.store.models import (
    CFReference,
    Node,
    NodeKind,
    NodeStatus,
    SQReference,
)


class NodeOperations(BlockWriter):
    """Node creation, updates, and reads."""

    def create_node(
        self,
        *,
        project_id: str,
        kind: NodeKind,
        title: str,
        parent_id: str | None = None,
        status: NodeStatus = NodeStatus.RUNNABLE,
        cf: CFReference | None = None,
        sq: SQReference | None = None,
    ) -> Node:
        """Create a node, optionally under a parent, and return it.

        Args:
            project_id: The project scope key. Required on every node.
            kind: What the node represents.
            title: Human-readable label.
            parent_id: The parent node, or ``None`` for a root.
            status: Initial status. Defaults to runnable.
            cf: Context Forge coordinates, held opaquely.
            sq: Squadron coordinates, held opaquely.

        Returns:
            The created node, with its store-generated id.

        Raises:
            NodeNotFoundError: If ``parent_id`` names no node.
            InvalidTransitionError: If ``status`` is a blocked status. A node
                is created unblocked and then blocked with ``block()``.
        """
        refuse_blocked_status(status, "create a node as")
        if parent_id is not None:
            self._require_node(parent_id)

        created = now()
        node = Node(
            id=new_id(),
            project_id=project_id,
            kind=kind,
            status=status,
            title=title,
            parent_id=parent_id,
            cf=cf if cf is not None else CFReference(),
            sq=sq if sq is not None else SQReference(),
            created_at=created,
            updated_at=created,
        )
        timestamp = isoformat(created)

        with self._connection:
            self._execute(
                sql.INSERT_NODE,
                (
                    node.id,
                    node.project_id,
                    node.parent_id,
                    node.kind.value,
                    node.status.value,
                    node.title,
                    node.cf.project,
                    node.cf.phase,
                    node.cf.slice_name,
                    node.cf.artifact_path,
                    node.sq.run_id,
                    node.sq.review_artifact_path,
                    node.sq.reviewed_sha,
                    timestamp,
                    timestamp,
                    node.cf.index,
                ),
            )

        return node

    def update_node_status(self, node_id: str, status: NodeStatus) -> Node:
        """Set a node's status, validating it against the vocabulary.

        Raises:
            NodeNotFoundError: If the node does not exist.
            ValueError: If ``status`` is outside the vocabulary.
            InvalidTransitionError: If the node is done (``done`` is terminal,
                so a done node takes no status write at all), is blocked, or
                ``status`` is a blocked status (those transitions belong to
                ``block()`` and ``resolve()``), or ``status`` is ``done`` while
                the node has an unresolved journal entry.
        """
        validated = NodeStatus(status)

        with self._connection:
            self._write_status(node_id, validated, isoformat(now()))

        return self._require_node(node_id)

    def update_cf_reference(self, node_id: str, cf: CFReference) -> Node:
        """Replace a node's CF reference fields. The node's id is unchanged.

        Every field is replaced, ``index`` included: a ``cf`` that leaves ``index``
        unset **clears the link**. To change one field, start from the node's own
        reference (``dataclasses.replace(node.cf, ...)``).

        Values are stored opaquely: the store never parses CF coordinates.
        """
        self._require_node(node_id)

        with self._connection:
            self._execute(
                sql.UPDATE_NODE_CF_REFERENCE,
                (
                    cf.project,
                    cf.phase,
                    cf.slice_name,
                    cf.artifact_path,
                    cf.index,
                    isoformat(now()),
                    node_id,
                ),
            )

        return self._require_node(node_id)

    def update_sq_reference(self, node_id: str, sq: SQReference) -> Node:
        """Replace a node's SQ reference fields. The node's id is unchanged.

        Values are stored opaquely: the store never parses Squadron output.
        """
        self._require_node(node_id)

        with self._connection:
            self._execute(
                sql.UPDATE_NODE_SQ_REFERENCE,
                (
                    sq.run_id,
                    sq.review_artifact_path,
                    sq.reviewed_sha,
                    isoformat(now()),
                    node_id,
                ),
            )

        return self._require_node(node_id)

    def nodes_for_project(self, project_id: str) -> list[Node]:
        """Return every node in a project, oldest first.

        Scoped to one project: nodes belonging to any other project are never
        returned. An empty result is not an error.
        """
        rows = self._execute(sql.SELECT_NODES_BY_PROJECT, (project_id,)).fetchall()
        return [map_node(row) for row in rows]

    def children_of(self, node_id: str) -> list[Node]:
        """Return the direct children of a node, oldest first."""
        rows = self._execute(sql.SELECT_CHILD_NODES, (node_id,)).fetchall()
        return [map_node(row) for row in rows]
