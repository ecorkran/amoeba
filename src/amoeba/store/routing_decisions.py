"""Routing decision, table-version and attempt-count reads.

Mixed into ``Store``; see ``store.py`` for the assembled public class.

Every read works through a read-only handle. Decisions, table versions and
counters are written only by ``record_routing_decision`` (D5). ``inputs``,
``route_parameters`` and table content are stored verbatim and shown by
inspection, so callers must not place secrets in them.
"""

from __future__ import annotations

from amoeba.store import sql_runner
from amoeba.store._base import StoreBase
from amoeba.store.mapping_runner import map_routing_decision, map_table_version
from amoeba.store.row_values import integer
from amoeba.store.runner_models import RoutingDecision, RoutingTableVersion


class RoutingDecisionOperations(StoreBase):
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
