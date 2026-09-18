"""The store: lifecycle, node CRUD, blocked states, and the two Runner queries.

This is the only module callers touch. It composes statements from ``sql``, maps
rows to the dataclasses in ``models``, and delegates schema setup to
``migrations`` at open time.

This library does **not** enforce single-writer. The resident process in slice
102 is what adds that; here the caller owns writer discipline. WAL journal mode
is set at open, giving concurrent readers alongside one writer.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from amoeba.store import paths, sql
from amoeba.store.mapping import map_blocked_state, map_node
from amoeba.store.migrations import migrate
from amoeba.store.models import (
    BLOCKED_KIND_TO_STATUS,
    BLOCKED_STATUSES,
    BlockedKind,
    BlockedNode,
    BlockedState,
    CFReference,
    InvalidTransitionError,
    Node,
    NodeKind,
    NodeNotFoundError,
    NodeStatus,
    SQReference,
    StoreBusyError,
    StoreCorruptError,
    StorePermissionError,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    """Generate an opaque node or blocked-state id.

    Deliberately not derived from CF coordinates: a node's CF pointers can
    change without the node becoming a different node.
    """
    return uuid.uuid4().hex


class Store:
    """A project-keyed lifecycle node store backed by one SQLite file.

    Open a store with :meth:`open` or :meth:`open_temporary`, both of which
    support the context-manager form::

        with Store.open(path) as store:
            store.create_node(project_id="demo", kind=NodeKind.SLICE, title="x")

    Every write raises on failure; no method returns a status code a caller can
    ignore.
    """

    def __init__(self, connection: sqlite3.Connection, path: Path) -> None:
        """Wrap an already-open, already-migrated connection.

        Callers use :meth:`open` or :meth:`open_temporary` instead.
        """
        self._connection = connection
        self._path = path

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def path(self) -> Path:
        """The store file this instance is backed by."""
        return self._path

    @classmethod
    def open(cls, path: Path | None = None, *, project_id: str | None = None) -> Self:
        """Open a store, creating and migrating it as needed.

        Args:
            path: The store file. When omitted, the central per-supervisor path
                for ``project_id`` is resolved from ``paths``.
            project_id: Used to resolve the central path when ``path`` is
                omitted. Ignored when ``path`` is given.

        Returns:
            An open store.

        Raises:
            ValueError: If neither ``path`` nor ``project_id`` is given.
            StorePermissionError: If the path or its parent cannot be created,
                read, or written. There is no fallback to a temporary location
                or an in-memory database.
            StoreCorruptError: If the file is not a readable SQLite database.
            StoreSchemaError: If the store is stamped newer than this code.
        """
        if path is None:
            if project_id is None:
                raise ValueError("open() requires either a path or a project_id")
            path = paths.store_path(project_id)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            # Specific: an unwritable or unreachable parent. Typed so no caller
            # mistakes it for a store that simply has no rows yet.
            logger.exception("cannot create store directory %s", path.parent)
            raise StorePermissionError(
                f"cannot create store directory {path.parent}: {error}"
            ) from error

        connection = cls._connect(path)

        try:
            migrate(connection)
        except Exception:
            connection.close()
            raise

        return cls(connection, path)

    @classmethod
    def open_temporary(cls) -> Self:
        """Open a throwaway in-memory store, for demos and the walkthrough.

        The store exists only for the lifetime of the connection and is never
        written to the central per-supervisor path.
        """
        path = Path(":memory:")
        connection = cls._connect(path)
        migrate(connection)
        return cls(connection, path)

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        """Connect, set WAL and the busy timeout, and verify readability."""
        try:
            connection = sqlite3.connect(
                path, timeout=sql.BUSY_TIMEOUT_SECONDS, isolation_level="DEFERRED"
            )
        except sqlite3.OperationalError as error:
            # Specific: sqlite3 reports an unopenable path this way. Typed so
            # the resolved path reaches the caller in the message.
            logger.exception("cannot open store at %s", path)
            raise StorePermissionError(
                f"cannot open store at {path}: {error}"
            ) from error

        try:
            connection.execute(sql.PRAGMA_JOURNAL_MODE)
            connection.execute(sql.PRAGMA_FOREIGN_KEYS_ON)
        except sqlite3.DatabaseError as error:
            connection.close()
            # Specific: a non-SQLite or malformed file fails on first real use.
            logger.exception("cannot configure store at %s", path)
            raise StoreCorruptError(f"cannot read store at {path}: {error}") from error

        return connection

    def close(self) -> None:
        """Close the underlying connection. Safe to call more than once."""
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the connection on normal and exception exit alike."""
        self.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _execute(self, statement: str, parameters: Sequence[object]) -> sqlite3.Cursor:
        """Execute one statement, translating lock contention to a typed error."""
        try:
            return self._connection.execute(statement, tuple(parameters))
        except sqlite3.OperationalError as error:
            if "locked" in str(error) or "busy" in str(error):
                # Specific: the busy timeout was exhausted. Never retried
                # indefinitely and never reported as an empty result.
                logger.exception("busy timeout exhausted")
                raise StoreBusyError(
                    f"busy timeout of {sql.BUSY_TIMEOUT_SECONDS}s exhausted: {error}"
                ) from error
            raise

    def _require_node(self, node_id: str) -> Node:
        node = self.get_node(node_id)
        if node is None:
            raise NodeNotFoundError(f"no node with id {node_id!r}")
        return node

    # ------------------------------------------------------------------
    # Node writes
    # ------------------------------------------------------------------

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
        """
        if parent_id is not None:
            self._require_node(parent_id)

        node = Node(
            id=_new_id(),
            project_id=project_id,
            kind=kind,
            status=status,
            title=title,
            parent_id=parent_id,
            cf=cf if cf is not None else CFReference(),
            sq=sq if sq is not None else SQReference(),
            created_at=_now(),
            updated_at=_now(),
        )

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
                    _isoformat(node.created_at),
                    _isoformat(node.updated_at),
                ),
            )

        return node

    def update_node_status(self, node_id: str, status: NodeStatus) -> Node:
        """Set a node's status, validating it against the vocabulary."""
        self._require_node(node_id)
        validated = NodeStatus(status)

        with self._connection:
            self._execute(
                sql.UPDATE_NODE_STATUS, (validated.value, _isoformat(_now()), node_id)
            )

        return self._require_node(node_id)

    def update_cf_reference(self, node_id: str, cf: CFReference) -> Node:
        """Replace a node's CF reference fields. The node's id is unchanged."""
        self._require_node(node_id)

        with self._connection:
            self._execute(
                sql.UPDATE_NODE_CF_REFERENCE,
                (
                    cf.project,
                    cf.phase,
                    cf.slice_name,
                    cf.artifact_path,
                    _isoformat(_now()),
                    node_id,
                ),
            )

        return self._require_node(node_id)

    def update_sq_reference(self, node_id: str, sq: SQReference) -> Node:
        """Replace a node's SQ reference fields. The node's id is unchanged."""
        self._require_node(node_id)

        with self._connection:
            self._execute(
                sql.UPDATE_NODE_SQ_REFERENCE,
                (
                    sq.run_id,
                    sq.review_artifact_path,
                    sq.reviewed_sha,
                    _isoformat(_now()),
                    node_id,
                ),
            )

        return self._require_node(node_id)

    # ------------------------------------------------------------------
    # Node reads
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Node | None:
        """Return the node with this id, or ``None`` if there is none.

        Raises:
            UnknownVocabularyValueError: If the stored row carries a value
                outside a closed vocabulary. Never a partially-populated object.
        """
        row = self._execute(sql.SELECT_NODE_BY_ID, (node_id,)).fetchone()
        return None if row is None else map_node(row)

    def nodes_for_project(self, project_id: str) -> list[Node]:
        """Return every node in a project, oldest first. Empty is not an error."""
        rows = self._execute(sql.SELECT_NODES_BY_PROJECT, (project_id,)).fetchall()
        return [map_node(row) for row in rows]

    def children_of(self, node_id: str) -> list[Node]:
        """Return the direct children of a node, oldest first."""
        rows = self._execute(sql.SELECT_CHILD_NODES, (node_id,)).fetchall()
        return [map_node(row) for row in rows]

    # ------------------------------------------------------------------
    # Blocked states — single operations, by design
    # ------------------------------------------------------------------

    def block(self, node_id: str, *, kind: BlockedKind, context: str) -> BlockedState:
        """Block a node: write the blocked state and set the node's status.

        One call, one transaction. There is deliberately no public path that
        writes one half, so node status and blocked state can never disagree.

        Args:
            node_id: The node to block.
            kind: What it is blocked on.
            context: Description of the block.

        Returns:
            The blocked state, with an unfilled resolution slot — that unfilled
            slot is the checkpoint.

        Raises:
            NodeNotFoundError: If the node does not exist.
            InvalidTransitionError: If the node is already blocked. Existing
                blocks are never silently overwritten.
        """
        node = self._require_node(node_id)
        if node.status in BLOCKED_STATUSES:
            raise InvalidTransitionError(
                f"node {node_id!r} is already blocked ({node.status.value})"
            )

        blocked = BlockedState(
            id=_new_id(),
            node_id=node_id,
            kind=kind,
            context=context,
            created_at=_now(),
            updated_at=_now(),
        )
        timestamp = _isoformat(blocked.created_at)

        with self._connection:
            self._execute(
                sql.INSERT_BLOCKED_STATE,
                (
                    blocked.id,
                    blocked.node_id,
                    blocked.kind.value,
                    blocked.context,
                    timestamp,
                    timestamp,
                ),
            )
            self._execute(
                sql.UPDATE_NODE_STATUS,
                (BLOCKED_KIND_TO_STATUS[kind].value, timestamp, node_id),
            )

        return blocked

    def resolve(self, node_id: str, *, resolved_by: str, detail: str) -> BlockedState:
        """Fill a node's resolution slot and flip it back to runnable.

        One call, one transaction, for the same reason :meth:`block` is.

        Args:
            node_id: The blocked node.
            resolved_by: Who supplied the resolution — its provenance.
            detail: What the resolution was.

        Returns:
            The resolved blocked state.

        Raises:
            NodeNotFoundError: If the node does not exist.
            InvalidTransitionError: If the node is not blocked.
        """
        node = self._require_node(node_id)
        if node.status not in BLOCKED_STATUSES:
            raise InvalidTransitionError(
                f"node {node_id!r} is not blocked ({node.status.value})"
            )

        resolved_at = _now()
        timestamp = _isoformat(resolved_at)

        with self._connection:
            cursor = self._execute(
                sql.FILL_RESOLUTION_SLOT,
                (resolved_by, detail, timestamp, timestamp, node_id),
            )
            if cursor.rowcount != 1:
                raise InvalidTransitionError(
                    f"node {node_id!r} has no open blocked state to resolve"
                )
            self._execute(
                sql.UPDATE_NODE_STATUS,
                (NodeStatus.RUNNABLE.value, timestamp, node_id),
            )

        state = self.blocked_state_for(node_id, include_resolved=True)
        if state is None:
            raise InvalidTransitionError(f"node {node_id!r} lost its blocked state")
        return state

    def blocked_state_for(
        self, node_id: str, *, include_resolved: bool = False
    ) -> BlockedState | None:
        """Return a node's open blocked state, or its most recent one."""
        if include_resolved:
            rows = self._execute(
                sql.SELECT_BLOCKED_STATES_FOR_NODE, (node_id,)
            ).fetchall()
            return map_blocked_state(rows[-1]) if rows else None

        row = self._execute(sql.SELECT_OPEN_BLOCKED_STATE, (node_id,)).fetchone()
        return None if row is None else map_blocked_state(row)

    # ------------------------------------------------------------------
    # The two Runner queries
    # ------------------------------------------------------------------

    def runnable(self, project_id: str) -> list[Node]:
        """What is runnable? Nodes awaiting work in this project.

        Scoped to one project: nodes belonging to any other project are never
        returned. An empty result means no runnable work, not an error.
        """
        rows = self._execute(
            sql.SELECT_RUNNABLE_NODES, (project_id, NodeStatus.RUNNABLE.value)
        ).fetchall()
        return [map_node(row) for row in rows]

    def blocked(self, project_id: str) -> list[BlockedNode]:
        """What is blocked, and on whom? Blocked nodes with their blockers.

        Each result carries its blocked-state record, so "on whom" is answered
        without a second call. Scoped to one project, like :meth:`runnable`.
        """
        statuses = sorted(status.value for status in BLOCKED_STATUSES)
        rows = self._execute(
            sql.select_blocked_nodes(len(statuses)), (project_id, *statuses)
        ).fetchall()

        node_width = len(sql.NODE_COLUMNS)
        return [
            BlockedNode(
                node=map_node(row[:node_width]),
                blocked_state=map_blocked_state(row[node_width:]),
            )
            for row in rows
        ]

    def all_blocked_states(self, node_id: str) -> Iterator[BlockedState]:
        """Every blocked state a node has had, oldest first."""
        rows = self._execute(sql.SELECT_BLOCKED_STATES_FOR_NODE, (node_id,)).fetchall()
        for row in rows:
            yield map_blocked_state(row)


def _isoformat(moment: datetime | None) -> str:
    """Render a timestamp for storage. ``None`` becomes the current time."""
    return (moment if moment is not None else _now()).isoformat()
