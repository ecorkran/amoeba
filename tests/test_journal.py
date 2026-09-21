"""Contract tests for the command journal store API.

These cover the claims recovery depends on. The ones that matter most are the
ordering guarantee (an entry is durable before the side effect), the atomicity
of escalation (outcome and block land together), and the already-blocked branch
— recovery reconciles against real state, so a wrong answer here is a wrong
answer at 3 a.m. after a crash.
"""

from __future__ import annotations

import pytest

from amoeba.store import (
    BlockedKind,
    CommandKind,
    InvalidTransitionError,
    JournalOutcome,
    JournalResolver,
    Node,
    NodeKind,
    NodeNotFoundError,
    NodeStatus,
    Store,
    sql_journal,
)

PROJECT = "demo"

SQ_PARAMETERS: dict[str, object] = {
    "pipeline": "p6",
    "params": {"slice": "102", "model": "opus"},
}
CF_PARAMETERS: dict[str, object] = {
    "project": "amoeba",
    "expected": {"developmentPhase": "Phase 6: Implementation"},
}


@pytest.fixture
def node(store: Store) -> Node:
    """A runnable node to journal commands against."""
    return store.create_node(
        project_id=PROJECT, kind=NodeKind.SLICE, title="resident process"
    )


def _journal_row_count(store: Store) -> int:
    """Count journal rows directly, to assert that nothing was written."""
    rows = store._connection.execute(  # pyright: ignore[reportPrivateUsage]
        f"SELECT COUNT(*) FROM {sql_journal.TABLE_COMMAND_JOURNAL}"
    ).fetchone()
    return int(rows[0])


def _open_blocked_state_count(store: Store, node_id: str) -> int:
    """How many unresolved blocked states a node carries."""
    return sum(
        1 for state in store.all_blocked_states(node_id) if not state.is_resolved
    )


# --------------------------------------------------------------------------
# journal_issue
# --------------------------------------------------------------------------


def test_issue_writes_an_unresolved_entry(store: Store, node: Node) -> None:
    """The committed entry is what recovery finds after a crash."""
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )

    assert entry.is_resolved is False
    assert entry.outcome is None
    assert entry.project_id == PROJECT
    assert entry.node_id == node.id
    assert entry.kind is CommandKind.SQ_RUN
    assert entry.issued_at is not None


def test_issue_commits_before_returning(store: Store, node: Node) -> None:
    """The ordering guarantee: the entry is durable by the time issue returns.

    Asserted by reading the row through a second, independent connection. A
    row visible to another connection has been committed — which is exactly
    what makes a crash immediately after this call recoverable.
    """
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )

    with Store.open(store.path) as reader:
        assert reader.journal_entry(entry.id) is not None


@pytest.mark.parametrize(
    ("kind", "parameters"),
    [
        (CommandKind.SQ_RUN, {"pipeline": "p6"}),
        (CommandKind.SQ_RUN, {"params": {"slice": "102"}}),
        (CommandKind.CF_WRITE, {"project": "amoeba"}),
        (CommandKind.CF_WRITE, {"expected": {"phase": "6"}}),
        (CommandKind.SQ_RUN, {}),
    ],
)
def test_issue_with_a_missing_required_parameter_raises_and_writes_nothing(
    store: Store, node: Node, kind: CommandKind, parameters: dict[str, object]
) -> None:
    """Validation precedes the write, so a rejected issue leaves no row.

    This is what stops a crash from surfacing an entry that recovery cannot
    reconcile because a matching field was never recorded.
    """
    with pytest.raises(ValueError, match="requires parameter keys"):
        store.journal_issue(node.id, kind=kind, parameters=parameters)

    assert _journal_row_count(store) == 0


def test_issue_against_an_unknown_node_raises(store: Store) -> None:
    """An entry always points at a real node; the foreign key is not the only guard."""
    with pytest.raises(NodeNotFoundError):
        store.journal_issue(
            "no-such-node", kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
        )

    assert _journal_row_count(store) == 0


def test_additional_parameter_keys_are_stored_unchanged(
    store: Store, node: Node
) -> None:
    """Keys beyond the required set survive the round trip untouched."""
    parameters: dict[str, object] = {
        **SQ_PARAMETERS,
        "issued_by": "runner",
        "nested": {"depth": [1, 2, {"three": True}]},
    }

    entry = store.journal_issue(node.id, kind=CommandKind.SQ_RUN, parameters=parameters)
    reloaded = store.journal_entry(entry.id)

    assert reloaded is not None
    assert reloaded.parameters == parameters


# --------------------------------------------------------------------------
# journal_resolve
# --------------------------------------------------------------------------


def test_resolve_closes_an_entry(store: Store, node: Node) -> None:
    """A resolved entry carries its outcome, result, and who closed it."""
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )

    resolved = store.journal_resolve(
        entry.id,
        outcome=JournalOutcome.COMPLETED,
        result={"run_id": "run-20260921-p6-abcd1234"},
    )

    assert resolved.is_resolved is True
    assert resolved.outcome is JournalOutcome.COMPLETED
    assert resolved.result == {"run_id": "run-20260921-p6-abcd1234"}
    assert resolved.resolved_by is JournalResolver.ISSUER
    assert resolved.resolved_at is not None


def test_resolve_records_the_recovery_resolver(store: Store, node: Node) -> None:
    """Recovery's writes are distinguishable from the issuer's."""
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )

    resolved = store.journal_resolve(
        entry.id,
        outcome=JournalOutcome.ADOPTED,
        result={"run_id": "run-1"},
        resolved_by=JournalResolver.RECOVERY,
    )

    assert resolved.resolved_by is JournalResolver.RECOVERY


def test_second_resolve_is_rejected(store: Store, node: Node) -> None:
    """A first outcome is never silently overwritten by a second."""
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )
    store.journal_resolve(entry.id, outcome=JournalOutcome.COMPLETED, result=None)

    with pytest.raises(InvalidTransitionError, match="already resolved"):
        store.journal_resolve(entry.id, outcome=JournalOutcome.FAILED, result=None)

    reloaded = store.journal_entry(entry.id)
    assert reloaded is not None
    assert reloaded.outcome is JournalOutcome.COMPLETED


def test_resolving_an_unknown_entry_raises(store: Store) -> None:
    """Resolving a nonexistent entry is a transition error, not a no-op."""
    with pytest.raises(InvalidTransitionError):
        store.journal_resolve(
            "no-such-entry", outcome=JournalOutcome.COMPLETED, result=None
        )


def test_result_mapping_round_trips_without_mutation(store: Store, node: Node) -> None:
    """Nested result structures survive storage unchanged."""
    result: dict[str, object] = {
        "run_id": "run-1",
        "schema_version": 4,
        "nested": {"list": [1, "two", None], "flag": False},
    }
    entry = store.journal_issue(
        node.id, kind=CommandKind.CF_WRITE, parameters=CF_PARAMETERS
    )

    store.journal_resolve(entry.id, outcome=JournalOutcome.ADOPTED, result=result)
    reloaded = store.journal_entry(entry.id)

    assert reloaded is not None
    assert reloaded.result == result


# --------------------------------------------------------------------------
# journal_escalate
# --------------------------------------------------------------------------


def test_escalate_marks_unknown_and_blocks_the_node(store: Store, node: Node) -> None:
    """Escalation is one transaction: the outcome and the block land together."""
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )

    escalated = store.journal_escalate(entry.id, reason="two candidate runs")

    assert escalated.outcome is JournalOutcome.UNKNOWN
    assert escalated.resolved_by is JournalResolver.RECOVERY

    reloaded_node = store.get_node(node.id)
    assert reloaded_node is not None
    assert reloaded_node.status is NodeStatus.BLOCKED_ON_HUMAN

    blocked_state = store.blocked_state_for(node.id)
    assert blocked_state is not None
    assert blocked_state.kind is BlockedKind.HUMAN


def test_escalated_blocked_state_context_names_the_entry(
    store: Store, node: Node
) -> None:
    """A human reading the block can find the journal entry behind it."""
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )

    store.journal_escalate(entry.id, reason="zero candidate runs")

    blocked_state = store.blocked_state_for(node.id)
    assert blocked_state is not None
    assert entry.id in blocked_state.context
    assert "zero candidate runs" in blocked_state.context


def test_escalate_against_an_already_blocked_node_writes_no_second_block(
    store: Store, node: Node
) -> None:
    """The already-blocked path marks the entry and stops there.

    This test would fail against an implementation that caught
    ``InvalidTransitionError`` from ``block()`` *after* opening its own
    transaction, and it is the reason the branch is explicit: the node is
    already stopped, so a second open blocked state would violate the unique
    partial index and there is nothing further to do.
    """
    store.block(node.id, kind=BlockedKind.JUDGE, context="awaiting a verdict")
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )

    escalated = store.journal_escalate(entry.id, reason="runs directory unreadable")

    assert escalated.outcome is JournalOutcome.UNKNOWN
    assert _open_blocked_state_count(store, node.id) == 1

    # The pre-existing block is the one left standing, untouched.
    blocked_state = store.blocked_state_for(node.id)
    assert blocked_state is not None
    assert blocked_state.kind is BlockedKind.JUDGE
    assert blocked_state.context == "awaiting a verdict"


def test_escalate_records_the_reason_in_the_result(store: Store, node: Node) -> None:
    """The reason survives on the entry, not only in the blocked-state context."""
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )

    escalated = store.journal_escalate(entry.id, reason="2 candidates")

    assert escalated.result is not None
    assert escalated.result["reason"] == "2 candidates"


def test_escalating_a_resolved_entry_raises(store: Store, node: Node) -> None:
    """An entry recovery already closed is not escalated a second time."""
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )
    store.journal_resolve(entry.id, outcome=JournalOutcome.ADOPTED, result=None)

    with pytest.raises(InvalidTransitionError, match="already resolved"):
        store.journal_escalate(entry.id, reason="should not apply")

    assert _open_blocked_state_count(store, node.id) == 0


def test_escalating_an_unknown_entry_raises(store: Store) -> None:
    """Escalating a nonexistent entry raises rather than blocking something."""
    with pytest.raises(InvalidTransitionError):
        store.journal_escalate("no-such-entry", reason="nothing to escalate")


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------


def test_unresolved_entries_are_returned_oldest_first(store: Store, node: Node) -> None:
    """Recovery consumes entries in issue order."""
    first = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )
    second = store.journal_issue(
        node.id, kind=CommandKind.CF_WRITE, parameters=CF_PARAMETERS
    )
    third = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )

    unresolved = store.unresolved_journal_entries(PROJECT)

    assert [entry.id for entry in unresolved] == [first.id, second.id, third.id]


def test_resolved_entries_disappear_from_the_unresolved_query(
    store: Store, node: Node
) -> None:
    """Only entries with a NULL outcome are recovery's business."""
    kept = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )
    closed = store.journal_issue(
        node.id, kind=CommandKind.CF_WRITE, parameters=CF_PARAMETERS
    )
    store.journal_resolve(closed.id, outcome=JournalOutcome.COMPLETED, result=None)

    unresolved = store.unresolved_journal_entries(PROJECT)

    assert [entry.id for entry in unresolved] == [kept.id]


def test_escalated_entries_disappear_from_the_unresolved_query(
    store: Store, node: Node
) -> None:
    """``unknown`` is an outcome: an escalated entry is resolved, not pending.

    This is what makes an interrupted recovery re-run only what is still open.
    """
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )
    store.journal_escalate(entry.id, reason="ambiguous")

    assert store.unresolved_journal_entries(PROJECT) == []


def test_unresolved_entries_are_project_scoped(store: Store, node: Node) -> None:
    """Another project's in-flight entries are never returned."""
    other = store.create_node(
        project_id="other", kind=NodeKind.SLICE, title="elsewhere"
    )
    store.journal_issue(other.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS)
    mine = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )

    assert [entry.id for entry in store.unresolved_journal_entries(PROJECT)] == [
        mine.id
    ]


def test_journal_entries_includes_resolved_by_default(store: Store, node: Node) -> None:
    """Inspection sees the whole history, not only what is in flight."""
    first = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )
    second = store.journal_issue(
        node.id, kind=CommandKind.CF_WRITE, parameters=CF_PARAMETERS
    )
    store.journal_resolve(first.id, outcome=JournalOutcome.COMPLETED, result=None)

    entries = store.journal_entries(PROJECT)

    assert [entry.id for entry in entries] == [first.id, second.id]


def test_journal_entries_can_exclude_resolved(store: Store, node: Node) -> None:
    """What ``inspect journal --unresolved`` consumes."""
    resolved = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )
    pending = store.journal_issue(
        node.id, kind=CommandKind.CF_WRITE, parameters=CF_PARAMETERS
    )
    store.journal_resolve(resolved.id, outcome=JournalOutcome.FAILED, result=None)

    entries = store.journal_entries(PROJECT, include_resolved=False)

    assert [entry.id for entry in entries] == [pending.id]


def test_journal_entries_can_filter_by_node(store: Store, node: Node) -> None:
    """A node's own command history, for inspection."""
    other_node = store.create_node(
        project_id=PROJECT, kind=NodeKind.SLICE, title="another slice"
    )
    mine = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )
    store.journal_issue(
        other_node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )

    entries = store.journal_entries(PROJECT, node_id=node.id)

    assert [entry.id for entry in entries] == [mine.id]


def test_journal_entries_filters_by_node_and_resolution_together(
    store: Store, node: Node
) -> None:
    """Both filters compose, rather than one silently winning."""
    store.journal_issue(node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS)
    closed = store.journal_issue(
        node.id, kind=CommandKind.CF_WRITE, parameters=CF_PARAMETERS
    )
    store.journal_resolve(closed.id, outcome=JournalOutcome.COMPLETED, result=None)

    entries = store.journal_entries(PROJECT, node_id=node.id, include_resolved=False)

    assert len(entries) == 1
    assert entries[0].is_resolved is False


def test_parameters_round_trip_through_the_reads(store: Store, node: Node) -> None:
    """Both queries decode the JSON columns identically."""
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )

    from_unresolved = store.unresolved_journal_entries(PROJECT)[0]
    from_listing = store.journal_entries(PROJECT)[0]

    assert from_unresolved.parameters == SQ_PARAMETERS
    assert from_listing.parameters == SQ_PARAMETERS
    assert from_unresolved.id == entry.id


def test_recorded_result_run_ids_reports_adopted_runs(store: Store, node: Node) -> None:
    """The matcher's fourth condition reads this: a run already claimed."""
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )
    store.journal_resolve(
        entry.id,
        outcome=JournalOutcome.ADOPTED,
        result={"run_id": "run-20260921-p6-abcd1234"},
        resolved_by=JournalResolver.RECOVERY,
    )

    assert store.recorded_result_run_ids(PROJECT) == {
        "run-20260921-p6-abcd1234": entry.id
    }


def test_recorded_result_run_ids_ignores_results_without_a_run_id(
    store: Store, node: Node
) -> None:
    """An escalation result carries a reason, not a run id."""
    entry = store.journal_issue(
        node.id, kind=CommandKind.SQ_RUN, parameters=SQ_PARAMETERS
    )
    store.journal_escalate(entry.id, reason="zero candidates")

    assert store.recorded_result_run_ids(PROJECT) == {}
