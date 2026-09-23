"""The store's one internal block writer.

Every blocked state is written here — by ``block()`` and by
``journal_escalate`` alike. One writer is what makes D3 hold: a ``HUMAN`` block
writes its ``escalation`` message in the same transaction, in exactly one
place, so no path can write a human block and miss its escalation.

A base class rather than a helper on ``StoreBase``, so the plumbing module stays
plumbing, and rather than a method on ``BlockingOperations``, so the journal
does not import a sibling operation class.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from amoeba.store import sql, sql_inbox
from amoeba.store._base import StoreBase, new_id
from amoeba.store.inbox_models import Channel
from amoeba.store.models import BLOCKED_KIND_TO_STATUS, BlockedKind

#: The blocker kinds that raise an escalation message. Only a human has a
#: channel; a judge or a Squadron checkpoint is resolved by the machinery that
#: blocked on it.
ESCALATING_KINDS: frozenset[BlockedKind] = frozenset({BlockedKind.HUMAN})


class BlockWriter(StoreBase):
    """Writes a block, its node status, and its escalation. Never commits."""

    def _write_block(
        self,
        node_id: str,
        *,
        project_id: str,
        kind: BlockedKind,
        context: str,
        timestamp: str,
        payload: Mapping[str, object] | None = None,
    ) -> str:
        """Write one blocked state, set the node's status, and escalate.

        Must be called **inside** the caller's transaction, so the block, the
        status, and the escalation land together or not at all. The caller has
        already checked that the node exists and is not blocked.

        Args:
            node_id: The node to block.
            project_id: The node's project, carried onto the escalation row.
            kind: What it is blocked on.
            context: Description of the block.
            timestamp: The instant, already rendered for storage.
            payload: Opaque data for whoever resolves the block. Stored on the
                escalation row; ignored for kinds that do not escalate.

        Returns:
            The new blocked state's id.
        """
        blocked_state_id = new_id()
        self._execute(
            sql.INSERT_BLOCKED_STATE,
            (blocked_state_id, node_id, kind.value, context, timestamp, timestamp),
        )
        self._execute(
            sql.UPDATE_NODE_STATUS,
            (BLOCKED_KIND_TO_STATUS[kind].value, timestamp, node_id),
        )
        if kind in ESCALATING_KINDS:
            self._write_escalation(
                node_id,
                project_id=project_id,
                blocked_state_id=blocked_state_id,
                timestamp=timestamp,
                payload=payload,
            )
        return blocked_state_id

    def _write_escalation(
        self,
        node_id: str,
        *,
        project_id: str,
        blocked_state_id: str,
        timestamp: str,
        payload: Mapping[str, object] | None = None,
    ) -> None:
        """Write one ``escalation`` row. Inside the caller's transaction."""
        self._execute(
            sql_inbox.INSERT_MESSAGE,
            (
                new_id(),
                project_id,
                Channel.ESCALATION.value,
                node_id,
                blocked_state_id,
                None,
                None,
                None if payload is None else json.dumps(dict(payload)),
                timestamp,
            ),
        )
