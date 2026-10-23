"""Shared staging for the routing-decision tests."""

from __future__ import annotations

import dataclasses

from amoeba.store import (
    REQUIRED_PARAMETER_KEYS,
    CommandKind,
    JournalOutcome,
    NodeKind,
    Route,
    RoutingDecisionInput,
    RoutingTableVersion,
    Store,
)

PROJECT = "demo"
TABLE = RoutingTableVersion(version="v1", content="rules v1")


def make_node(store: Store, project_id: str = PROJECT) -> str:
    return store.create_node(project_id=project_id, kind=NodeKind.SLICE, title="n").id


def issue_entry(store: Store, node_id: str, *, resolved: bool = True) -> str:
    """Issue a journal entry on a node, and resolve it unless told not to."""
    entry = store.journal_issue(
        node_id,
        kind=CommandKind.SQ_RUN,
        parameters=dict.fromkeys(REQUIRED_PARAMETER_KEYS[CommandKind.SQ_RUN], "v"),
    )
    if resolved:
        store.journal_resolve(entry.id, outcome=JournalOutcome.COMPLETED)
    return entry.id


def decision_input(
    node_id: str, entry_id: str | None = None, **changes: object
) -> RoutingDecisionInput:
    base = RoutingDecisionInput(
        project_id=PROJECT,
        node_id=node_id,
        journal_entry_id=entry_id,
        inputs={"outcome": "completed"},
        rule_id="rule-1",
        table_version=TABLE.version,
        amoeba_version="0.1",
        route=Route.ADVANCE,
        route_parameters={"limit": 3},
    )
    return dataclasses.replace(base, **changes)  # type: ignore[arg-type]
