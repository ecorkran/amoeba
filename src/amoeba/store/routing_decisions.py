"""Routing decision, table-version and attempt-count reads.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

Every read works through a read-only handle. Decisions, table versions and
counters are written only by ``record_routing_decision`` (D5). ``inputs``,
``route_parameters`` and table content are stored verbatim and shown by
inspection, so callers must not place secrets in them.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from amoeba.store import sql_journal, sql_runner
from amoeba.store._block_writer import BlockWriter, refuse_blocked_status
from amoeba.store.journal_models import JournalEntry
from amoeba.store.mapping_journal import map_journal_entry
from amoeba.store.mapping_runner import map_routing_decision, map_table_version
from amoeba.store.models import InvalidTransitionError, NodeNotFoundError, NodeStatus
from amoeba.store.row_values import integer
from amoeba.store.runner_models import (
    BlockEffect,
    Route,
    RoutingDecision,
    RoutingDecisionInput,
    RoutingTableVersion,
    StatusEffect,
)


@dataclass(frozen=True)
class _ValidatedDecision:
    """A decision's checked, encoded values, ready to write."""

    route: Route
    inputs_json: str
    route_parameters_json: str


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must be non-empty text")


def _encode(value: Mapping[str, object], name: str) -> str:
    try:
        return json.dumps(dict(value))
    except TypeError as error:
        # Specific: a value that is not JSON-serializable is a caller error,
        # reported as the ValueError every malformed write raises.
        raise ValueError(f"{name} is not JSON-serializable: {error}") from error


def _check_values(
    decision: RoutingDecisionInput,
    table: RoutingTableVersion,
    effect: StatusEffect | BlockEffect | None,
    attempt_step: str | None,
) -> _ValidatedDecision:
    """The checks that need no store: field shape, encoding, vocabulary."""
    _require_text(decision.project_id, "project_id")
    _require_text(decision.rule_id, "rule_id")
    _require_text(decision.table_version, "table_version")
    _require_text(decision.amoeba_version, "amoeba_version")
    if attempt_step is not None:
        _require_text(attempt_step, "attempt_step")
    if table.version != decision.table_version:
        raise ValueError(
            f"table version {table.version!r} does not match the decision's "
            f"{decision.table_version!r}"
        )
    if isinstance(effect, StatusEffect):
        refuse_blocked_status(
            NodeStatus(effect.status), "record a decision moving a node into"
        )
    return _ValidatedDecision(
        route=Route(decision.route),
        inputs_json=_encode(decision.inputs, "inputs"),
        route_parameters_json=_encode(decision.route_parameters, "route_parameters"),
    )


class RoutingDecisionOperations(BlockWriter):
    """Reads over ``routing_decisions``, ``routing_table_versions`` and counters."""

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
                blocked status.
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
