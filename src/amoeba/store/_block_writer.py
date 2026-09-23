"""The store's one internal block writer.

Every blocked state is written here — by ``block()`` and by
``journal_escalate`` alike. One writer is what makes D3 hold: whatever must
accompany a block is written in exactly one place, so no path can write a block
and miss it.

A base class rather than a helper on ``StoreBase``, so the plumbing module stays
plumbing, and rather than a method on ``BlockingOperations``, so the journal
does not import a sibling operation class.
"""

from __future__ import annotations

from collections.abc import Mapping

from amoeba.store import sql
from amoeba.store._base import StoreBase, new_id
from amoeba.store.models import BLOCKED_KIND_TO_STATUS, BlockedKind


class BlockWriter(StoreBase):
    """Writes a blocked state and its node status. Never opens a transaction."""

    def _write_block(
        self,
        node_id: str,
        *,
        kind: BlockedKind,
        context: str,
        timestamp: str,
        payload: Mapping[str, object] | None = None,
    ) -> str:
        """Write one blocked state and set the node's blocked status.

        Must be called **inside** the caller's transaction, so the block lands
        together with whatever else that caller writes, or not at all. The
        caller has already checked that the node exists and is not blocked.

        Args:
            node_id: The node to block.
            kind: What it is blocked on.
            context: Description of the block.
            timestamp: The instant, already rendered for storage.
            payload: Opaque data for whoever resolves the block.

        Returns:
            The new blocked state's id.
        """
        del payload  # no column holds it until the escalation row is written
        blocked_state_id = new_id()
        self._execute(
            sql.INSERT_BLOCKED_STATE,
            (blocked_state_id, node_id, kind.value, context, timestamp, timestamp),
        )
        self._execute(
            sql.UPDATE_NODE_STATUS,
            (BLOCKED_KIND_TO_STATUS[kind].value, timestamp, node_id),
        )
        return blocked_state_id
