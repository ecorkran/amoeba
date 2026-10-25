"""Rows for the ``routing-decisions`` listing.

Each row is one recorded routing decision, with whether the stored table version
still gives the same answer on the recorded inputs (D6). The store is read-only,
so this works whether or not the resident process is running.
"""

from __future__ import annotations

from typing import Final

from amoeba.inspection.listing import NODE_OPTION, ListingRequest, Row
from amoeba.runner.routing.inputs import INPUT_ATTEMPT, RoutingInput
from amoeba.runner.routing.recompute import recompute
from amoeba.store import RoutingDecision, Store

ROUTING_DECISION_COLUMNS: Final = (
    "decided_at",
    "node_id",
    "step",
    "rule_id",
    "route",
    "attempt",
    "table_version",
    "recomputes",
)

#: How much of a table version label a table row shows; ``--json`` shows it all.
SHORT_VERSION_LENGTH: Final = 12

RECOMPUTES_YES: Final = "yes"
RECOMPUTES_NO: Final = "no"
RECOMPUTES_ERROR_PREFIX: Final = "error: "


def routing_decision_rows(store: Store, request: ListingRequest) -> list[Row]:
    """A project's routing decisions, oldest first, optionally for one node."""
    node_id = request.option(NODE_OPTION)
    node_ids = (
        [node_id]
        if node_id is not None
        else [node.id for node in store.nodes_for_project(request.require_project_id())]
    )
    decisions = sorted(
        (decision for node in node_ids for decision in store.routing_decisions(node)),
        key=lambda decision: decision.decided_at,
    )
    return [_row(store, decision, request.compact) for decision in decisions]


def _row(store: Store, decision: RoutingDecision, compact: bool) -> Row:
    version = decision.table_version
    return {
        "decided_at": decision.decided_at.isoformat(),
        "node_id": decision.node_id,
        "step": decision.inputs.get(RoutingInput.STEP.value),
        "rule_id": decision.rule_id,
        "route": decision.route.value,
        "attempt": decision.inputs.get(INPUT_ATTEMPT),
        "table_version": version[:SHORT_VERSION_LENGTH] if compact else version,
        "recomputes": _recomputes(store, decision),
    }


def _recomputes(store: Store, decision: RoutingDecision) -> str:
    stored = store.routing_table_version(decision.table_version)
    if stored is None:
        return f"{RECOMPUTES_ERROR_PREFIX}no stored table {decision.table_version}"
    result = recompute(decision, stored)
    if result.error is not None:
        return f"{RECOMPUTES_ERROR_PREFIX}{result.error}"
    return RECOMPUTES_YES if result.matches else RECOMPUTES_NO
