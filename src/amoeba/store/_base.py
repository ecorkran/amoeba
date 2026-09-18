"""Connection plumbing shared by the store's operation mixins.

The store's public surface is one class, ``Store``, but its operations split by
concern across modules to keep each file near the ~300-line guideline. Every
part needs the same three things: the connection, statement execution that
translates lock contention into a typed error, and node lookup that raises on
absence. They live here so no mixin imports another.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from amoeba.store import sql
from amoeba.store.mapping import map_node
from amoeba.store.models import Node, NodeNotFoundError, StoreBusyError

logger = logging.getLogger(__name__)

#: SQLite result codes meaning "the lock could not be acquired in time".
#: Matched on the error *code*, never on the message text: a message-substring
#: check misclassifies unrelated errors, since "blocked_states" contains
#: "locked".
BUSY_ERROR_CODES = frozenset({sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED})


def now() -> datetime:
    """The current instant, in UTC."""
    return datetime.now(UTC)


def isoformat(moment: datetime | None) -> str:
    """Render a timestamp for storage. ``None`` becomes the current time."""
    return (moment if moment is not None else now()).isoformat()


def new_id() -> str:
    """Generate an opaque node or blocked-state id.

    Deliberately not derived from CF coordinates: a node's CF pointers can
    change without the node becoming a different node.
    """
    return uuid.uuid4().hex


class StoreBase:
    """Connection state and the helpers every operation mixin builds on."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        busy_timeout_seconds: float = sql.BUSY_TIMEOUT_SECONDS,
    ) -> None:
        self._connection = connection
        self._busy_timeout_seconds = busy_timeout_seconds

    def _execute(self, statement: str, parameters: Sequence[object]) -> sqlite3.Cursor:
        """Execute one statement, translating lock contention to a typed error."""
        try:
            return self._connection.execute(statement, tuple(parameters))
        except sqlite3.OperationalError as error:
            if error.sqlite_errorcode in BUSY_ERROR_CODES:
                # Specific: the busy timeout was exhausted. Never retried
                # indefinitely and never reported as an empty result.
                logger.exception("busy timeout exhausted")
                raise StoreBusyError(
                    f"busy timeout of {self._busy_timeout_seconds}s exhausted "
                    f"on {statement.strip().split(maxsplit=1)[0]}: {error}"
                ) from error
            raise

    def get_node(self, node_id: str) -> Node | None:
        """Return the node with this id, or ``None`` if there is none.

        Raises:
            UnknownVocabularyValueError: If the stored row carries a value
                outside a closed vocabulary. Never a partially-populated object.
        """
        row = self._execute(sql.SELECT_NODE_BY_ID, (node_id,)).fetchone()
        return None if row is None else map_node(row)

    def _require_node(self, node_id: str) -> Node:
        """Return a node, raising when it does not exist."""
        node = self.get_node(node_id)
        if node is None:
            raise NodeNotFoundError(f"no node with id {node_id!r}")
        return node
