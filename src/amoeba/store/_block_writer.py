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

from amoeba.store import sql, sql_inbox, sql_journal
from amoeba.store._base import StoreBase, new_id
from amoeba.store.inbox_models import Channel
from amoeba.store.models import (
    BLOCKED_KIND_TO_STATUS,
    BLOCKED_STATUSES,
    BlockedKind,
    InvalidTransitionError,
    Node,
    NodeStatus,
    StoreIntegrityError,
)
from amoeba.store.runner_models import BlockEffect, StatusEffect

#: The blocker kinds that raise an escalation message. Only a human has a
#: channel; a judge or a Squadron checkpoint is resolved by the machinery that
#: blocked on it.
ESCALATING_KINDS: frozenset[BlockedKind] = frozenset({BlockedKind.HUMAN})


def refuse_blocked_status(status: NodeStatus, action: str) -> None:
    """Reject a node write that would touch the blocked half on its own.

    Blocked statuses are owned by ``block()`` and ``resolve()``, which write
    status and blocked state in one transaction. Refusing them here is what
    makes "no public path writes one half" structural rather than advisory.
    """
    if status in BLOCKED_STATUSES:
        raise InvalidTransitionError(
            f"cannot {action} {status.value!r} directly: "
            "use block() and resolve() so status and blocked state agree"
        )


class BlockWriter(StoreBase):
    """Writes a block, its node status, and its escalation. Never commits."""

    def _refuse_done(self, node_id: str) -> None:
        """Refuse any status write on a ``done`` node. The one terminal check.

        ``done`` is terminal (D1), so every writer of ``nodes.status`` that can
        reach a done node calls this before writing.

        Raises:
            NodeNotFoundError: If the node does not exist.
            InvalidTransitionError: If the node is ``done``.
        """
        self._refuse_if_done(self._require_node(node_id))

    def _refuse_if_done(self, node: Node) -> None:
        """:meth:`_refuse_done` for a caller that already holds the node."""
        if node.status is NodeStatus.DONE:
            raise InvalidTransitionError(
                f"node {node.id!r} is done, and done is terminal"
            )

    def _refuse_if_blocked(self, node: Node) -> None:
        """Refuse to block a node that is already blocked.

        The check ``block()`` makes before its transaction, and a routing
        decision's ``BlockEffect`` makes before its own. ``_write_block``
        assumes its caller has made it.

        Raises:
            InvalidTransitionError: If the node is already blocked. Existing
                blocks are never silently overwritten.
        """
        if node.status in BLOCKED_STATUSES:
            raise InvalidTransitionError(
                f"node {node.id!r} is already blocked ({node.status.value})"
            )

    def _write_status(self, node_id: str, status: NodeStatus, timestamp: str) -> None:
        """Set a node's status through the rules every status write follows.

        Runs inside the caller's transaction and never commits. It is the one
        status write ``update_node_status`` and a routing decision's
        ``StatusEffect`` share, so neither can skip a rule.

        Raises:
            NodeNotFoundError: If the node does not exist.
            InvalidTransitionError: If the node is done (any target status), is
                blocked, the target is a blocked status, or the target is
                ``done`` while the node has an unresolved journal entry.
        """
        current = self._require_node(node_id)
        self._refuse_if_done(current)
        refuse_blocked_status(current.status, "move a node out of")
        refuse_blocked_status(status, "move a node into")
        if status is NodeStatus.DONE:
            entry = self._execute(
                sql_journal.SELECT_UNRESOLVED_ENTRY_FOR_NODE,
                (current.project_id, node_id),
            ).fetchone()
            if entry is not None:
                raise InvalidTransitionError(
                    f"cannot mark node {node_id!r} done: journal entry "
                    f"{entry[0]!r} is unresolved"
                )
        self._execute(sql.UPDATE_NODE_STATUS, (status.value, timestamp, node_id))

    def _apply_effect(
        self,
        node_id: str,
        *,
        project_id: str,
        effect: StatusEffect | BlockEffect | None,
        timestamp: str,
        journal_entry_id: str | None,
    ) -> None:
        """Apply a routing decision's or a resolution's effect, in the caller's
        transaction. The one place both read, so neither can skip a rule.
        """
        if isinstance(effect, StatusEffect):
            self._write_status(node_id, NodeStatus(effect.status), timestamp)
        elif isinstance(effect, BlockEffect):
            # The refusal block() makes, checked here under the write lock.
            self._refuse_if_blocked(self._require_node(node_id))
            self._write_block(
                node_id,
                project_id=project_id,
                kind=BlockedKind.HUMAN,
                context=effect.context,
                timestamp=timestamp,
                payload=effect.payload,
                journal_entry_id=journal_entry_id,
            )

    def _write_block(
        self,
        node_id: str,
        *,
        project_id: str,
        kind: BlockedKind,
        context: str,
        timestamp: str,
        payload: Mapping[str, object] | None = None,
        journal_entry_id: str | None = None,
    ) -> str:
        """Write one blocked state, set the node's status, and escalate.

        Must be called **inside** the caller's transaction, so the block, the
        status, and the escalation land together or not at all. The caller has
        already checked that the node exists and is not blocked; this method
        refuses a done node itself, before any write.

        Args:
            node_id: The node to block.
            project_id: The node's project, carried onto the escalation row.
            kind: What it is blocked on.
            context: Description of the block.
            timestamp: The instant, already rendered for storage.
            payload: Opaque data for whoever resolves the block. Stored on the
                escalation row; ignored for kinds that do not escalate.
            journal_entry_id: Set when recovery raised the block.

        Returns:
            The new blocked state's id.
        """
        self._refuse_done(node_id)
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
                journal_entry_id=journal_entry_id,
            )
        return blocked_state_id

    def _write_resolution(
        self,
        node_id: str,
        *,
        resolved_by: str,
        detail: str,
        timestamp: str,
        decision: str | None = None,
        instructions: str | None = None,
        awaits_runner: bool = False,
    ) -> bool:
        """Fill a node's open resolution slot and flip it back to runnable.

        Inside the caller's transaction, like :meth:`_write_block`, so that
        ``resolve()`` and ``apply_submission`` both write a resolution through
        one place without opening a second transaction. It needs no done check:
        it acts only on a blocked node, and a done node is never blocked.

        ``awaits_runner`` is set only on the inbox path: a PM's resolution is
        the Runner's to answer, while ``resolve()`` is the Runner's own write
        and has no one to answer it (slice 127, D9).

        Returns:
            Whether an open slot was filled. ``False`` means the node had no
            open blocked state, and nothing was written.
        """
        cursor = self._execute(
            sql.FILL_RESOLUTION_SLOT,
            (
                resolved_by,
                detail,
                timestamp,
                timestamp,
                decision,
                instructions,
                1 if awaits_runner else None,
                node_id,
            ),
        )
        if cursor.rowcount != 1:
            return False
        self._execute(
            sql.UPDATE_NODE_STATUS, (NodeStatus.RUNNABLE.value, timestamp, node_id)
        )
        return True

    def _escalate_existing_block(
        self,
        node_id: str,
        *,
        project_id: str,
        journal_entry_id: str,
        timestamp: str,
    ) -> str:
        """Escalate against a node's **existing** open block, writing no block.

        Recovery's already-blocked branch: the node is stopped already, so no
        second block is written, but whatever it is blocked on — human or not —
        a human must now also hear that a command's outcome is unknown.

        Returns:
            The existing open blocked state's id, which the row points at.

        Raises:
            StoreIntegrityError: If the node has no open blocked state, which
                its blocked status says it must. Raised inside the caller's
                transaction, so nothing lands.
        """
        row = self._execute(sql.SELECT_OPEN_BLOCKED_STATE, (node_id,)).fetchone()
        if row is None:
            raise StoreIntegrityError(
                f"node {node_id!r} is blocked but has no open blocked state"
            )
        blocked_state_id = str(row[0])
        self._write_escalation(
            node_id,
            project_id=project_id,
            blocked_state_id=blocked_state_id,
            timestamp=timestamp,
            journal_entry_id=journal_entry_id,
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
        journal_entry_id: str | None = None,
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
                journal_entry_id,
                None,
                None if payload is None else json.dumps(dict(payload)),
                timestamp,
            ),
        )
