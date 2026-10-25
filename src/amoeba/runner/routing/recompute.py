"""Recompute a decision from its record and its stored table version alone (D6).

It checks the table's application: the stored table text, evaluated on the inputs
the decision recorded. The reduction from raw evidence is the reducer's own tests'
job, and the evidence stays in the store, linked by ``journal_entry_id``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from amoeba.runner.routing.engine import evaluate
from amoeba.runner.routing.inputs import RoutingInputs
from amoeba.runner.routing.table import TableError, parse_table
from amoeba.store import Route, RoutingDecision, RoutingTableVersion


@dataclass(frozen=True)
class Recomputation:
    """What the stored table gives for a decision's inputs.

    ``error`` is set, and the rest empty, when the decision cannot be recomputed
    (an unparseable stored table, inputs outside today's vocabulary). That is not
    a mismatch: ``matches`` is only meaningful when ``error`` is ``None``.
    """

    rule_id: str | None
    route: Route | None
    matches: bool
    error: str | None = None


def recompute(decision: RoutingDecision, stored: RoutingTableVersion) -> Recomputation:
    """Evaluate ``stored``'s table on ``decision``'s inputs and compare."""
    try:
        table = _parsed(stored.content)
    except TableError as error:
        # Expected: a table stored under a grammar this code no longer reads.
        # An unreadable table is shown as an error, never as a mismatch.
        return _unreadable(f"stored table {stored.version}: {error}")
    try:
        inputs = RoutingInputs.from_record(decision.inputs)
        match = evaluate(table, inputs)
    except ValueError as error:
        # Expected: recorded inputs outside today's vocabulary, or a table no rule
        # of which applies. Both mean "cannot recompute", not "decided wrongly".
        return _unreadable(str(error))
    return Recomputation(
        rule_id=match.rule.id,
        route=match.route,
        matches=(match.rule.id, match.route) == (decision.rule_id, decision.route),
    )


#: A listing recomputes many decisions under few table versions; parsing each
#: stored text once is enough. Tables are immutable, and a failed parse is not
#: cached (the exception propagates).
_parsed = lru_cache(maxsize=16)(parse_table)


def _unreadable(reason: str) -> Recomputation:
    return Recomputation(rule_id=None, route=None, matches=False, error=reason)
