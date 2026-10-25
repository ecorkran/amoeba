"""Match a table against an outcome's inputs, and turn the route into an effect.

Both functions are pure. This module and ``validate.py`` are the only places a
``Route`` member is compared, so a route is never chosen in a code branch outside
the table (a source test holds that line). The eligibility predicates restrict a
route; they never choose one. What happens after a rerun limit is simply the next
rule that matches, which the table decides.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from amoeba.runner.ingest.outcome import PAYLOAD_REASON, PAYLOAD_RUN_ID
from amoeba.runner.routing.inputs import (
    NODE_RUNNABLE,
    UNKNOWN,
    RoutingInput,
    RoutingInputs,
)
from amoeba.runner.routing.table import RoutingTable, Rule
from amoeba.store import BlockEffect, NodeStatus, Route, StatusEffect

#: Why a node is blocked by a routing decision, and the rest of that payload.
REASON_ROUTED: Final = "routed"
PAYLOAD_RULE_ID: Final = "rule_id"
PAYLOAD_TABLE_VERSION: Final = "table_version"
PAYLOAD_JUDGE_ELIGIBLE: Final = "judge_eligible"


@dataclass(frozen=True)
class Match:
    """The rule an outcome matched, its route, and the parameters to record."""

    rule: Rule
    route: Route
    parameters: Mapping[str, int | bool]


def _runnable(inputs: RoutingInputs) -> bool:
    return inputs.values[RoutingInput.NODE_STATE] == NODE_RUNNABLE


def _advance_eligible(rule: Rule, inputs: RoutingInputs) -> bool:
    return _runnable(inputs)


def _rerun_eligible(rule: Rule, inputs: RoutingInputs) -> bool:
    """A step runs at most ``max_attempts`` times through rerun rules.

    An outcome whose attempts cannot be counted (unknown step) is never rerun.
    """
    if not _runnable(inputs) or inputs.values[RoutingInput.STEP] == UNKNOWN:
        return False
    if inputs.attempt is None or rule.max_attempts is None:
        return False
    return inputs.attempt < rule.max_attempts


def _escalate_eligible(rule: Rule, inputs: RoutingInputs) -> bool:
    return True


#: One eligibility predicate per route, defined once.
ELIGIBILITY: Final[Mapping[Route, Callable[[Rule, RoutingInputs], bool]]] = (
    MappingProxyType(
        {
            Route.ADVANCE: _advance_eligible,
            Route.RERUN: _rerun_eligible,
            Route.ESCALATE: _escalate_eligible,
        }
    )
)


def _matches(rule: Rule, inputs: RoutingInputs) -> bool:
    """Every input the rule names has a value in its set; others are free.

    ``unknown`` satisfies a condition only when the condition names it.
    """
    return all(inputs.values[name] in values for name, values in rule.when.items())


def evaluate(table: RoutingTable, inputs: RoutingInputs) -> Match:
    """The first rule, in file order, that matches and whose route is eligible.

    Raises:
        ValueError: Nothing applied. Load validation makes this impossible, since
            the catch-all escalate always matches and is always eligible.
    """
    for rule in table.rules:
        if _matches(rule, inputs) and ELIGIBILITY[rule.route](rule, inputs):
            return Match(rule, rule.route, rule.parameters)
    raise ValueError(
        f"no rule of table {table.version} applies to {dict(inputs.values)}"
    )


def effect_for(
    match: Match,
    inputs: RoutingInputs,
    *,
    table_version: str,
    run_id: str,
) -> StatusEffect | BlockEffect | None:
    """The store effect of a route; the one place a route becomes an effect (D5).

    An escalate on a node that is not runnable needs none: ingestion's block
    already stands, and a done node takes no writes.
    """
    if match.route is Route.ADVANCE:
        return StatusEffect(NodeStatus.DONE)
    if match.route is Route.ESCALATE and _runnable(inputs):
        return BlockEffect(
            context=f"routed by {match.rule.id}",
            payload={
                PAYLOAD_REASON: REASON_ROUTED,
                PAYLOAD_RULE_ID: match.rule.id,
                PAYLOAD_TABLE_VERSION: table_version,
                PAYLOAD_RUN_ID: run_id,
                PAYLOAD_JUDGE_ELIGIBLE: match.rule.judge_eligible,
            },
        )
    # A rerun changes nothing: the step stays runnable and the next tick reissues it.
    return None
