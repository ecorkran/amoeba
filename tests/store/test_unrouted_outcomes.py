"""``awaits_routing``: set by issuer resolutions of ``sq_run``, read oldest first.

The store decides the flag (slice 125, D8): no caller passes it, so no caller can
forget it. Recovery resolutions leave it null, because the Runner did not
observe an outcome.
"""

from __future__ import annotations

import sqlite3

import pytest
from evidence_harness import PROJECT, seed_node
from sq_run_fixtures import sq_run_parameters

from amoeba.store import (
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
    Store,
    sql_journal,
)

OTHER_PROJECT = "elsewhere"
CF_PARAMETERS: dict[str, object] = {
    "project": "p",
    "expected": {},
    "checkout": "/work/p",
}


def _issue_run(store: Store, node_id: str, run_id: str) -> JournalEntry:
    return store.journal_issue(
        node_id,
        kind=CommandKind.SQ_RUN,
        parameters=sq_run_parameters({"pipeline": "p6", "params": {}}, run_id=run_id),
    )


@pytest.mark.parametrize("outcome", [JournalOutcome.COMPLETED, JournalOutcome.FAILED])
def test_an_issuer_resolution_of_an_sq_run_sets_the_flag(
    store: Store, outcome: JournalOutcome
) -> None:
    entry = _issue_run(store, seed_node(store), "run-1")
    assert entry.awaits_routing is False

    resolved = store.journal_resolve(entry.id, outcome=outcome, result={})

    assert resolved.awaits_routing is True
    assert [e.id for e in store.unrouted_outcomes(PROJECT)] == [entry.id]


@pytest.mark.parametrize(
    "outcome",
    [JournalOutcome.ADOPTED, JournalOutcome.NOT_APPLIED, JournalOutcome.UNKNOWN],
)
def test_a_recovery_resolution_leaves_the_flag_null(
    store: Store, outcome: JournalOutcome
) -> None:
    entry = _issue_run(store, seed_node(store), "run-1")

    resolved = store.journal_resolve(
        entry.id, outcome=outcome, result={}, resolved_by=JournalResolver.RECOVERY
    )

    assert resolved.awaits_routing is False
    assert store.unrouted_outcomes(PROJECT) == []


def test_an_escalation_leaves_the_flag_null(store: Store) -> None:
    entry = _issue_run(store, seed_node(store), "run-1")

    escalated = store.journal_escalate(entry.id, reason="cannot tell")

    assert escalated.awaits_routing is False
    assert store.unrouted_outcomes(PROJECT) == []


def test_a_resolved_cf_write_does_not_await_routing(store: Store) -> None:
    entry = store.journal_issue(
        seed_node(store), kind=CommandKind.CF_WRITE, parameters=CF_PARAMETERS
    )

    resolved = store.journal_resolve(entry.id, outcome=JournalOutcome.COMPLETED)

    assert resolved.awaits_routing is False
    assert store.unrouted_outcomes(PROJECT) == []


def test_unrouted_outcomes_are_oldest_issued_first_and_project_scoped(
    store: Store,
) -> None:
    node_id = seed_node(store)
    other_node_id = seed_node(store, OTHER_PROJECT)
    first = _issue_run(store, node_id, "run-1")
    second = _issue_run(store, node_id, "run-2")
    elsewhere = _issue_run(store, other_node_id, "run-3")
    # Resolved in the opposite order to issue: the order is by issue time.
    for entry in (second, elsewhere, first):
        store.journal_resolve(entry.id, outcome=JournalOutcome.COMPLETED, result={})

    assert [e.id for e in store.unrouted_outcomes(PROJECT)] == [first.id, second.id]
    assert [e.id for e in store.unrouted_outcomes(OTHER_PROJECT)] == [elsewhere.id]


def test_the_unrouted_query_is_served_by_its_partial_index(store: Store) -> None:
    with sqlite3.connect(store.path) as connection:
        plan = connection.execute(
            f"EXPLAIN QUERY PLAN {sql_journal.SELECT_UNROUTED_OUTCOMES}", (PROJECT,)
        ).fetchall()

    assert sql_journal.INDEX_JOURNAL_AWAITS_ROUTING in " ".join(
        str(row[-1]) for row in plan
    )
