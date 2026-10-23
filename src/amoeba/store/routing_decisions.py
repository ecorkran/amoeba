"""Routing decisions, table versions and attempt counts: the write and the reads.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

``record_routing_decision`` (D5) is the only writer of decisions, table versions
and counters; it validates, then writes them and the node effect in one
transaction. Every read works through a read-only handle. ``inputs``,
``route_parameters`` and table content are stored verbatim and shown by
inspection, so callers must not place secrets in them.
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.store import sql_inbox, sql_journal, sql_runner
from amoeba.store._base import isoformat, new_id, now
from amoeba.store._block_writer import BlockWriter
from amoeba.store.journal_models import JournalEntry
from amoeba.store.mapping_journal import map_journal_entry
from amoeba.store.mapping_runner import map_routing_decision, map_table_version
from amoeba.store.models import (
    BlockedKind,
    InvalidTransitionError,
    NodeNotFoundError,
    NodeStatus,
    StoreIntegrityError,
)
from amoeba.store.row_values import integer
from amoeba.store.runner_models import (
    BlockEffect,
    Route,
    RoutingDecision,
    RoutingDecisionInput,
    RoutingTableVersion,
    StatusEffect,
)
from amoeba.store.write_values import encode_object, require_text


@dataclass(frozen=True)
class _ValidatedDecision:
    """A decision's checked, encoded values, ready to write."""

    route: Route
    inputs_json: str
    route_parameters_json: str


def _check_values(
    decision: RoutingDecisionInput,
    table: RoutingTableVersion,
    effect: StatusEffect | BlockEffect | None,
    attempt_step: str | None,
) -> _ValidatedDecision:
    """The checks that need no store: field shape, encoding, vocabulary."""
    require_text(decision.project_id, "project_id")
    require_text(decision.rule_id, "rule_id")
    require_text(decision.table_version, "table_version")
    require_text(decision.amoeba_version, "amoeba_version")
    if attempt_step is not None:
        require_text(attempt_step, "attempt_step")
    if table.version != decision.table_version:
        raise ValueError(
            f"table version {table.version!r} does not match the decision's "
            f"{decision.table_version!r}"
        )
    return _ValidatedDecision(
        route=Route(decision.route),
        inputs_json=encode_object(decision.inputs, "inputs"),
        route_parameters_json=encode_object(
            decision.route_parameters, "route_parameters"
        ),
    )


class RoutingDecisionOperations(BlockWriter):
    """Records routing decisions, and reads them, table versions and counters."""

    def routing_decision(self, decision_id: str) -> RoutingDecision | None:
        """One decision by id, or ``None``."""
        row = self._execute(sql_runner.SELECT_DECISION_BY_ID, (decision_id,)).fetchone()
        return None if row is None else map_routing_decision(row)

    def routing_decision_for_entry(
        self, journal_entry_id: str
    ) -> RoutingDecision | None:
        """The decision that routed a journal entry, or ``None``."""
        row = self._execute(
            sql_runner.SELECT_DECISION_BY_ENTRY, (journal_entry_id,)
        ).fetchone()
        return None if row is None else map_routing_decision(row)

    def routing_decisions(self, node_id: str) -> list[RoutingDecision]:
        """Every decision recorded on a node, oldest first."""
        rows = self._execute(sql_runner.SELECT_DECISIONS_BY_NODE, (node_id,)).fetchall()
        return [map_routing_decision(row) for row in rows]

    def routing_table_version(self, version: str) -> RoutingTableVersion | None:
        """The stored routing table with this version label, or ``None``.

        With a decision, this is everything needed to recompute the decision.
        """
        row = self._execute(sql_runner.SELECT_TABLE_VERSION, (version,)).fetchone()
        return None if row is None else map_table_version(row)

    def attempt_count(self, node_id: str, step: str) -> int:
        """How many attempts decisions have counted for a node and step.

        A pair with no row returns ``0``. That is the true count, not a
        fallback: nothing has been counted yet.
        """
        row = self._execute(sql_runner.SELECT_ATTEMPT_COUNT, (node_id, step)).fetchone()
        return 0 if row is None else integer(row[0], sql_runner.COL_ATTEMPT_COUNT)

    def record_routing_decision(
        self,
        decision: RoutingDecisionInput,
        *,
        table: RoutingTableVersion,
        effect: StatusEffect | BlockEffect | None,
        attempt_step: str | None,
    ) -> RoutingDecision:
        """Record a routing decision and its effect in one transaction.

        In order: store ``table`` if its version is new; insert the decision;
        when ``attempt_step`` is given, increment the ``(node, step)`` counter
        and record the new count on the decision; apply ``effect``. A failure at
        any step leaves none of them. Which route takes which effect, and when
        an attempt counts, is the Runner's; the store checks none of it.

        Args:
            decision: The decision. ``inputs``, ``route_parameters`` and the
                table content are stored verbatim and shown by inspection, so
                callers must not place secrets in them.
            table: The routing table version the decision used.
            effect: ``StatusEffect`` follows ``update_node_status``'s rules;
                ``BlockEffect`` writes a ``HUMAN`` block and its escalation.
            attempt_step: The step to count an attempt against, or ``None``.

        Returns:
            The stored decision.

        Raises:
            ValueError: A field is malformed (see the validation).
            NodeNotFoundError: The node is not in the project.
            InvalidTransitionError: The journal entry is missing or in another
                project; or the effect is refused (a done or blocked node, a
                blocked target status, or ``done`` with an unresolved entry).
            StoreIntegrityError: The entry already has a decision, or the
                version exists with different content.
        """
        # Validation reads the node and entry before the lock is taken. That is
        # safe: nothing deletes either, so they cannot vanish in between, and
        # every check that depends on mutable state (a done or blocked node,
        # an unresolved entry) is repeated by the effect under the lock.
        validated = self._validate_routing_decision(
            decision, table=table, effect=effect, attempt_step=attempt_step
        )
        decision_id = new_id()
        timestamp = isoformat(now())

        with self._connection:
            # Takes the write lock before the counter is read, so the count the
            # decision records is the count the increment produces.
            self._execute(sql_inbox.BEGIN_IMMEDIATE, ())
            self._store_table_version(table, timestamp)
            count = None
            if attempt_step is not None:
                count = self.attempt_count(decision.node_id, attempt_step) + 1
            self._execute(
                sql_runner.INSERT_DECISION,
                (
                    decision_id,
                    decision.project_id,
                    decision.node_id,
                    decision.journal_entry_id,
                    validated.inputs_json,
                    decision.rule_id,
                    decision.table_version,
                    decision.amoeba_version,
                    validated.route.value,
                    validated.route_parameters_json,
                    attempt_step,
                    count,
                    timestamp,
                ),
            )
            if attempt_step is not None:
                self._execute(
                    sql_runner.UPSERT_ATTEMPT_COUNT,
                    (decision.node_id, attempt_step, timestamp),
                )
            self._apply_effect(decision, effect, timestamp)
            stored = self.routing_decision(decision_id)

        if stored is None:
            raise StoreIntegrityError(f"routing decision {decision_id!r} vanished")
        return stored

    def _store_table_version(self, table: RoutingTableVersion, timestamp: str) -> None:
        """Insert a table version on first use; refuse changed content."""
        existing = self.routing_table_version(table.version)
        if existing is None:
            self._execute(
                sql_runner.INSERT_TABLE_VERSION,
                (table.version, table.content, timestamp),
            )
        elif existing.content != table.content:
            raise StoreIntegrityError(
                f"routing table version {table.version!r} is already stored with "
                "different content; change the version label with the content"
            )

    def _apply_effect(
        self,
        decision: RoutingDecisionInput,
        effect: StatusEffect | BlockEffect | None,
        timestamp: str,
    ) -> None:
        """Apply a decision's effect inside the caller's transaction."""
        if isinstance(effect, StatusEffect):
            self._write_status(decision.node_id, NodeStatus(effect.status), timestamp)
        elif isinstance(effect, BlockEffect):
            # The refusal block() makes, checked here under the write lock.
            self._refuse_if_blocked(self._require_node(decision.node_id))
            self._write_block(
                decision.node_id,
                project_id=decision.project_id,
                kind=BlockedKind.HUMAN,
                context=effect.context,
                timestamp=timestamp,
                payload=effect.payload,
                journal_entry_id=decision.journal_entry_id,
            )

    def _validate_routing_decision(
        self,
        decision: RoutingDecisionInput,
        *,
        table: RoutingTableVersion,
        effect: StatusEffect | BlockEffect | None,
        attempt_step: str | None,
    ) -> _ValidatedDecision:
        """Check a decision before any transaction opens.

        Raises:
            ValueError: A text field is empty, ``inputs`` or ``route_parameters``
                is not JSON-serializable, ``attempt_step`` is given but empty,
                the route or an effect status is outside its vocabulary, or
                ``table.version`` differs from the decision's.
            NodeNotFoundError: The node is not in the project.
            InvalidTransitionError: ``journal_entry_id`` names an entry that is
                missing or in another project, or a ``StatusEffect`` targets a
                blocked status. (An effect the node's state refuses is raised
                later, inside the transaction.)
        """
        validated = _check_values(decision, table, effect, attempt_step)
        node = self.get_node(decision.node_id)
        if node is None or node.project_id != decision.project_id:
            raise NodeNotFoundError(
                f"no node {decision.node_id!r} in project {decision.project_id!r}"
            )
        if decision.journal_entry_id is not None:
            self._require_entry_in_project(
                decision.journal_entry_id, decision.project_id
            )
        return validated

    def _require_entry_in_project(self, entry_id: str, project_id: str) -> JournalEntry:
        row = self._execute(
            sql_journal.SELECT_JOURNAL_ENTRY_BY_ID, (entry_id,)
        ).fetchone()
        entry = None if row is None else map_journal_entry(row)
        if entry is None or entry.project_id != project_id:
            raise InvalidTransitionError(
                f"journal entry {entry_id!r} does not exist in project {project_id!r}"
            )
        return entry
