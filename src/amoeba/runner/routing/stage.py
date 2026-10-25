"""The route stage: one decision for every outcome awaiting routing (D5).

Store reads and pure computations, then one ``record_routing_decision`` per entry,
which lands the decision, the attempt increment and the node effect in one
transaction. There is no ``except`` here: a store failure and any other exception
propagate to the tick and the tenant (122's boundary), leaving the entry unrouted.
"""

from __future__ import annotations

from amoeba.runner.faults import NodeContext
from amoeba.runner.ingest.record import entry_run_id
from amoeba.runner.routing.engine import effect_for, evaluate
from amoeba.runner.routing.evidence import gather
from amoeba.runner.routing.inputs import UNKNOWN, RoutingInput
from amoeba.runner.routing.reduce import reduce
from amoeba.runner.routing.table import RoutingTable
from amoeba.store import (
    JournalEntry,
    RoutingDecisionInput,
    RoutingTableVersion,
    Store,
)


def route_outcomes(
    store: Store,
    project_id: str,
    routing: RoutingTable,
    amoeba_version: str,
    context: NodeContext,
) -> bool:
    """Route every unrouted outcome of the project, oldest first.

    Returns:
        Whether anything was written.
    """
    wrote = False
    for entry in store.unrouted_outcomes(project_id):
        # So 122's catch blocks the node whose outcome failed to route.
        context.set(entry.node_id)
        _route(store, entry, routing, amoeba_version)
        wrote = True
    return wrote


def _route(
    store: Store, entry: JournalEntry, routing: RoutingTable, amoeba_version: str
) -> None:
    inputs = reduce(gather(store, entry))
    match = evaluate(routing, inputs)
    run_id = entry_run_id(entry)
    step = inputs.values[RoutingInput.STEP]
    store.record_routing_decision(
        RoutingDecisionInput(
            project_id=entry.project_id,
            node_id=entry.node_id,
            journal_entry_id=entry.id,
            inputs=inputs.to_record(),
            rule_id=match.rule.id,
            table_version=routing.version,
            amoeba_version=amoeba_version,
            route=match.route,
            route_parameters=dict(match.parameters),
        ),
        table=RoutingTableVersion(routing.version, routing.content),
        effect=effect_for(match, inputs, table_version=routing.version, run_id=run_id),
        # Every decision on a known step counts one attempt (D5).
        attempt_step=None if step == UNKNOWN else step,
    )
