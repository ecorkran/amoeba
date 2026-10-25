"""Load-time validation of a routing table file (D4).

Every problem is collected and reported together, naming the rule id where there
is one. ``validate`` checks which grammar each route accepts and never chooses a
route, which is what the "no route chosen outside the engine" rule protects.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

from amoeba.runner.lifecycle.steps import STEP_MAP
from amoeba.runner.routing.inputs import VALUE_SETS, RoutingInput
from amoeba.store import Route

if TYPE_CHECKING:
    from amoeba.runner.routing.table import RuleFile, TableFile

#: The table grammar versions this code can read. A stored table keeps its own.
SUPPORTED_FORMATS: Final = frozenset({1})

#: The one outcome an ``advance`` or ``rerun`` rule may name.
ONLY_OUTCOME: Final = frozenset({"completed"})

#: The parameter each route takes, defined once. ``advance`` takes none.
PARAMETER_MAX_ATTEMPTS: Final = "max_attempts"
PARAMETER_JUDGE_ELIGIBLE: Final = "judge_eligible"
ROUTE_PARAMETERS: Final[Mapping[Route, frozenset[str]]] = {
    Route.ADVANCE: frozenset(),
    Route.RERUN: frozenset({PARAMETER_MAX_ATTEMPTS}),
    Route.ESCALATE: frozenset({PARAMETER_JUDGE_ELIGIBLE}),
}

#: Routes that take the run's evidence as it stands, so only a finished run fits.
COMPLETED_ONLY_ROUTES: Final = frozenset({Route.ADVANCE, Route.RERUN})


def normalize_value(raw: str | bool) -> str:
    """A condition value as compared: trimmed and lower-cased.

    YAML reads ``true``, ``false``, ``yes`` and ``no`` as booleans, so a bare
    ``at_loop: true`` arrives as ``True`` and is read as the value ``true``.
    """
    if isinstance(raw, bool):
        return "true" if raw else "false"
    return raw.strip().lower()


def normalize_condition(raw: str | bool | Sequence[str | bool]) -> frozenset[str]:
    """One value or a list of values, as a set of normalized values."""
    if isinstance(raw, (str, bool)):
        return frozenset({normalize_value(raw)})
    return frozenset(normalize_value(item) for item in raw)


def normalize_input_name(raw: str) -> str:
    return raw.strip().lower()


def validate(table: TableFile) -> list[str]:
    """Every problem with ``table``, in file order; empty when it is loadable."""
    problems: list[str] = []
    if table.format not in SUPPORTED_FORMATS:
        supported = ", ".join(str(item) for item in sorted(SUPPORTED_FORMATS))
        problems.append(f"format {table.format} is not supported (use {supported})")
    problems.extend(_time_bound_problems(table.time_bounds_minutes))
    problems.extend(_id_problems(table.rules))
    for rule in table.rules:
        problems.extend(_rule_problems(rule))
    problems.extend(_ending_problems(table.rules))
    return problems


def _time_bound_problems(bounds: Mapping[str, int]) -> list[str]:
    needed = {spec.pipeline for spec in STEP_MAP.values() if spec.pipeline}
    problems = [
        f"time_bounds_minutes lacks a bound for pipeline {pipeline}"
        for pipeline in sorted(needed - bounds.keys())
    ]
    problems += [
        f"time_bounds_minutes names {pipeline}, which no step runs"
        for pipeline in sorted(bounds.keys() - needed)
    ]
    problems += [
        f"time_bounds_minutes {pipeline} must be positive, got {minutes}"
        for pipeline, minutes in bounds.items()
        if minutes < 1
    ]
    return problems


def _id_problems(rules: Sequence[RuleFile]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for position, rule in enumerate(rules, start=1):
        if not rule.id.strip():
            problems.append(f"rule {position} has an empty id")
        elif rule.id in seen:
            problems.append(f"rule id {rule.id!r} is used twice")
        seen.add(rule.id)
    return problems


def _rule_problems(rule: RuleFile) -> list[str]:
    label = f"rule {rule.id!r}"
    conditions, problems = _condition_problems(label, rule)
    route = _route_of(rule.route)
    if route is None:
        names = ", ".join(member.value for member in Route)
        return [*problems, f"{label}: route {rule.route!r} is not one of {names}"]
    problems += _parameter_problems(label, route, rule)
    if route in COMPLETED_ONLY_ROUTES:
        outcome = conditions.get(RoutingInput.OUTCOME)
        if outcome != ONLY_OUTCOME:
            problems.append(
                f"{label}: a {route.value} rule must name outcome: completed "
                "and nothing else for outcome"
            )
    return problems


def normalize_route(text: str) -> Route:
    """The ``Route`` a table's route text names (trimmed, case-insensitive).

    Raises:
        ValueError: The text names no route.
    """
    return Route(text.strip().lower())


def _route_of(text: str) -> Route | None:
    try:
        return normalize_route(text)
    except ValueError:
        # Expected: the table names a route this code does not have. It is
        # reported as a problem, not raised.
        return None


def _condition_problems(
    label: str, rule: RuleFile
) -> tuple[dict[RoutingInput, frozenset[str]], list[str]]:
    """The rule's conditions, keyed by input, and every problem found in them."""
    conditions: dict[RoutingInput, frozenset[str]] = {}
    problems: list[str] = []
    for raw_name, raw_values in rule.when.items():
        name = _input_of(raw_name)
        if name is None:
            problems.append(f"{label}: {raw_name!r} is not a routing input")
            continue
        values = normalize_condition(raw_values)
        conditions[name] = values
        problems += [
            f"{label}: {name.value} has no value {value!r}"
            for value in sorted(values - VALUE_SETS[name])
        ]
    return conditions, problems


def _input_of(text: str) -> RoutingInput | None:
    try:
        return RoutingInput(normalize_input_name(text))
    except ValueError:
        # Expected: the table names an input this code does not have (for
        # example gate_state before slice 128). Reported as a problem.
        return None


def _parameter_problems(label: str, route: Route, rule: RuleFile) -> list[str]:
    given = {
        name
        for name, value in (
            (PARAMETER_MAX_ATTEMPTS, rule.max_attempts),
            (PARAMETER_JUDGE_ELIGIBLE, rule.judge_eligible),
        )
        if value is not None
    }
    allowed = ROUTE_PARAMETERS[route]
    problems = [
        f"{label}: a {route.value} rule takes no {name}"
        for name in sorted(given - allowed)
    ]
    problems += [
        f"{label}: a {route.value} rule needs {name}"
        for name in sorted(allowed - given)
    ]
    if rule.max_attempts is not None and rule.max_attempts < 1:
        problems.append(f"{label}: max_attempts must be at least 1")
    return problems


def _ending_problems(rules: Sequence[RuleFile]) -> list[str]:
    if not rules:
        return ["the table has no rules; it must end in a catch-all escalate"]
    problems = [
        f"rule {rule.id!r} has an empty when but is not last; it would hide every "
        "rule after it"
        for rule in rules[:-1]
        if not rule.when
    ]
    last = rules[-1]
    if last.when or _route_of(last.route) is not Route.ESCALATE:
        problems.append(
            f"the last rule {last.id!r} must be a catch-all: an empty when "
            "and route escalate"
        )
    return problems
