"""Blocked-state operations and the two Runner queries.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

``block()`` and ``resolve()`` are each a single store operation in a single
transaction. There is deliberately no public path that writes one half, because
node status and blocked state must never disagree — making that the store's
responsibility rather than the caller's is what guarantees it. This is the
schema-level expression of checkpoint-as-persisted-blocked-state.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping

from amoeba.store import sql, sql_inbox
from amoeba.store._base import isoformat, now
from amoeba.store._block_writer import BlockWriter
from amoeba.store.mapping import map_blocked_state, map_node
from amoeba.store.models import (
    BLOCKED_STATUSES,
    BlockedKind,
    BlockedNode,
    BlockedState,
    InvalidTransitionError,
    Node,
    NodeStatus,
    ResolutionOutcome,
)
from amoeba.store.runner_models import BlockEffect, StatusEffect


class BlockingOperations(BlockWriter):
    """Blocking, resolution, and the queries the Runner's loop consumes."""

    def block(
        self,
        node_id: str,
        *,
        kind: BlockedKind,
        context: str,
        payload: Mapping[str, object] | None = None,
    ) -> BlockedState:
        """Block a node: write the blocked state and set the node's status.

        One call, one transaction.

        Args:
            node_id: The node to block.
            kind: What it is blocked on.
            context: Description of the block.
            payload: Opaque data for whoever resolves the block. Optional.

        Returns:
            The blocked state, with an unfilled resolution slot — that unfilled
            slot is the checkpoint.

        Raises:
            NodeNotFoundError: If the node does not exist.
            InvalidTransitionError: If the node is already blocked. Existing
                blocks are never silently overwritten.
        """
        node = self._require_node(node_id)
        self._refuse_if_blocked(node)

        created = now()

        with self._connection:
            blocked_state_id = self._write_block(
                node_id,
                project_id=node.project_id,
                kind=kind,
                context=context,
                timestamp=isoformat(created),
                payload=payload,
            )

        return BlockedState(
            id=blocked_state_id,
            node_id=node_id,
            kind=kind,
            context=context,
            created_at=created,
            updated_at=created,
        )

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
            InvalidTransitionError: If the node is not blocked, or has no open
                blocked state to resolve.
        """
        node = self._require_node(node_id)
        if node.status not in BLOCKED_STATUSES:
            raise InvalidTransitionError(
                f"node {node_id!r} is not blocked ({node.status.value})"
            )

        timestamp = isoformat(now())

        with self._connection:
            filled = self._write_resolution(
                node_id, resolved_by=resolved_by, detail=detail, timestamp=timestamp
            )
            if not filled:
                raise InvalidTransitionError(
                    f"node {node_id!r} has no open blocked state to resolve"
                )

        state = self.blocked_state_for(node_id, include_resolved=True)
        if state is None:
            raise InvalidTransitionError(f"node {node_id!r} lost its blocked state")
        return state

    def blocked_state_for(
        self, node_id: str, *, include_resolved: bool = False
    ) -> BlockedState | None:
        """Return a node's open blocked state, or its most recent one.

        Args:
            node_id: The node to inspect.
            include_resolved: When true, return the most recent blocked state
                even if it has been resolved. Otherwise only an open one.

        Returns:
            The blocked state, or ``None`` when there is no matching one.
        """
        if include_resolved:
            rows = self._execute(
                sql.SELECT_BLOCKED_STATES_FOR_NODE, (node_id,)
            ).fetchall()
            return map_blocked_state(rows[-1]) if rows else None

        row = self._execute(sql.SELECT_OPEN_BLOCKED_STATE, (node_id,)).fetchone()
        return None if row is None else map_blocked_state(row)

    def all_blocked_states(self, node_id: str) -> Iterator[BlockedState]:
        """Every blocked state a node has had, oldest first."""
        rows = self._execute(sql.SELECT_BLOCKED_STATES_FOR_NODE, (node_id,)).fetchall()
        for row in rows:
            yield map_blocked_state(row)

    def runnable(self, project_id: str) -> list[Node]:
        """What is runnable? Nodes awaiting work in this project.

        Uses the ``(project_id, status)`` index. Scoped to one project: nodes
        belonging to any other project are never returned. An empty result means
        no runnable work, not an error.
        """
        rows = self._execute(
            sql.SELECT_RUNNABLE_NODES, (project_id, NodeStatus.RUNNABLE.value)
        ).fetchall()
        return [map_node(row) for row in rows]

    def blocked(self, project_id: str) -> list[BlockedNode]:
        """What is blocked, and on whom? Blocked nodes with their blockers.

        Each result carries its blocked-state record, so "on whom" is answered
        without a second call. Uses the same ``(project_id, status)`` index and
        is project-scoped exactly as :meth:`runnable` is.
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

    def pending_resolutions(self, project_id: str) -> list[BlockedState]:
        """The project's PM resolutions the Runner has not yet answered.

        Oldest resolution first. Served by the partial index on the flag, so
        the cost follows the unanswered rows, not the history (slice 127, D9).
        """
        rows = self._execute(sql.SELECT_PENDING_RESOLUTIONS, (project_id,)).fetchall()
        return [map_blocked_state(row) for row in rows]

    def blocked_state(self, blocked_state_id: str) -> BlockedState | None:
        """One blocked state by id, open or resolved, or ``None``."""
        row = self._execute(sql.SELECT_BLOCKED_STATE_BY_ID, (blocked_state_id,))
        found = row.fetchone()
        return None if found is None else map_blocked_state(found)

    def acknowledge_resolution(
        self,
        blocked_state_id: str,
        *,
        outcome: ResolutionOutcome,
        code: str | None = None,
        reason: str | None = None,
        effect: StatusEffect | BlockEffect | None = None,
    ) -> None:
        """Record the Runner's answer to a resolution, with its effect.

        One transaction: the outcome, code and reason are recorded, the flag is
        cleared, and ``effect`` is applied through the writers a routing
        decision uses. An effect that fails rolls the whole answer back, so the
        flag stays set and nothing is written.

        Args:
            blocked_state_id: The resolved, flagged blocked state.
            outcome: ``applied`` or ``rejected``.
            code: The rejection code. Required with ``rejected``, forbidden with
                ``applied``.
            reason: The rejection detail, for people. Same rule as ``code``.
            effect: What the answer does to the node, if anything.

        Raises:
            ValueError: ``rejected`` without a code and a reason, or ``applied``
                with a code or a reason.
            InvalidTransitionError: The blocked state does not exist, is
                unresolved, or is not awaiting the Runner; or the effect is
                refused.
        """
        answered = code is not None and reason is not None
        unanswered = code is None and reason is None
        if outcome is ResolutionOutcome.REJECTED and not answered:
            raise ValueError("a rejected resolution takes a code and a reason")
        if outcome is ResolutionOutcome.APPLIED and not unanswered:
            raise ValueError("an applied resolution takes no code and no reason")
        timestamp = isoformat(now())
        with self._connection:
            # Takes the write lock before the flag is read, as a routing
            # decision does, so two answers cannot both see it set.
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            row = self._execute(
                sql.SELECT_BLOCKED_STATE_BY_ID, (blocked_state_id,)
            ).fetchone()
            state = None if row is None else map_blocked_state(row)
            if state is None or not state.awaits_runner:
                raise InvalidTransitionError(
                    f"blocked state {blocked_state_id!r} is not a resolution "
                    "awaiting the Runner"
                )
            node = self._require_node(state.node_id)
            self._execute(
                sql.ACKNOWLEDGE_RESOLUTION,
                (outcome.value, code, reason, timestamp, blocked_state_id),
            )
            self._apply_effect(
                node.id,
                project_id=node.project_id,
                effect=effect,
                timestamp=timestamp,
                journal_entry_id=None,
            )
