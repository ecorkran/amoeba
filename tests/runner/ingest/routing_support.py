"""The stand-in for slice 126's router: record a routing decision for an entry.

126 does not exist yet, so tests that need an outcome routed call the store's
``record_routing_decision`` through this one helper. It decides nothing: it writes
the decision the store needs to clear the entry's ``awaits_routing`` flag.
"""

from __future__ import annotations

from routing_helpers import TABLE, decision_input

from amoeba.store import RoutingDecision, Store


def route_outcome(
    store: Store, project_id: str, node_id: str, journal_entry_id: str
) -> RoutingDecision:
    """Record an ``advance`` decision for ``journal_entry_id`` with no effect."""
    return store.record_routing_decision(
        decision_input(node_id, journal_entry_id, project_id=project_id),
        table=TABLE,
        effect=None,
        attempt_step=None,
    )
