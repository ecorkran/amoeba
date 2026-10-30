"""Escalating an unexpected fault: node block or project-scoped row."""

from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest
from sq_run_fixtures import LEGACY_ENTRY_ID, insert_legacy_sq_run_entry

from amoeba.runner import faults
from amoeba.runner.faults import (
    Fault,
    FaultKind,
    NodeContext,
    TickFaults,
    escalate,
    raise_expected_faults,
)
from amoeba.runner.launch import PARAM_PARAMS, PARAM_PIPELINE
from amoeba.store import (
    PARAM_RUN_ID,
    BlockedKind,
    CommandKind,
    Node,
    NodeKind,
    NodeStatus,
    Store,
)

PROJECT = "demo"
ERROR = RuntimeError("planner exploded")


@pytest.fixture
def node(store: Store) -> Node:
    return store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")


def _in(node_id: str | None) -> NodeContext:
    context = NodeContext()
    if node_id is not None:
        context.set(node_id)
    return context


def _escalate(store: Store, context: NodeContext) -> None:
    escalate(store, PROJECT, context, FaultKind.UNEXPECTED_FAULT, ERROR)


def test_a_free_node_is_blocked_on_a_human_with_the_fault_named(
    store: Store, node: Node
) -> None:
    _escalate(store, _in(node.id))

    blocked = store.blocked_state_for(node.id)
    assert blocked is not None and blocked.kind is BlockedKind.HUMAN
    assert (
        "unexpected_fault" in blocked.context and "planner exploded" in blocked.context
    )
    assert store.open_project_escalations(PROJECT) == []


def test_an_already_blocked_node_gets_nothing_more(store: Store, node: Node) -> None:
    store.block(node.id, kind=BlockedKind.HUMAN, context="earlier")
    before = len(list(store.all_blocked_states(node.id)))

    _escalate(store, _in(node.id))
    _escalate(store, _in(node.id))

    assert len(list(store.all_blocked_states(node.id))) == before
    assert store.open_project_escalations(PROJECT) == []


@pytest.mark.parametrize("kind", [BlockedKind.SQ_CHECKPOINT, BlockedKind.JUDGE])
def test_a_node_blocked_on_a_non_human_kind_still_escalates_to_the_project(
    store: Store, node: Node, kind: BlockedKind
) -> None:
    store.block(node.id, kind=kind, context="earlier")
    before = len(list(store.all_blocked_states(node.id)))

    _escalate(store, _in(node.id))

    assert len(list(store.all_blocked_states(node.id))) == before
    [row] = store.open_project_escalations(PROJECT)
    assert row.fault_kind == "unexpected_fault"


def test_a_node_with_a_run_in_flight_takes_the_project_path(
    store: Store, node: Node
) -> None:
    entry = store.journal_issue(
        node.id,
        kind=CommandKind.SQ_RUN,
        parameters={PARAM_PIPELINE: "p", PARAM_PARAMS: {}, PARAM_RUN_ID: "run-1"},
    )

    _escalate(store, _in(node.id))

    assert store.blocked_state_for(node.id) is None
    [row] = store.open_project_escalations(PROJECT)
    assert row.fault_kind == "unexpected_fault"
    assert row.payload is not None
    assert row.payload["node_id"] == node.id
    assert row.payload["run_ids"] == ["run-1"]
    assert entry.id  # the entry stays unresolved


def test_a_done_node_takes_the_project_path(store: Store, node: Node) -> None:
    store.update_node_status(node.id, NodeStatus.DONE)

    _escalate(store, _in(node.id))

    assert store.blocked_state_for(node.id) is None
    [row] = store.open_project_escalations(PROJECT)
    assert row.payload is not None and row.payload["node_id"] == node.id


def test_no_node_in_context_takes_the_project_path(store: Store) -> None:
    _escalate(store, _in(None))

    [row] = store.open_project_escalations(PROJECT)
    assert row.payload is not None and row.payload["node_id"] is None


def test_a_repeated_fault_adds_no_rows(store: Store) -> None:
    _escalate(store, _in(None))
    _escalate(store, _in(None))

    assert len(store.open_project_escalations(PROJECT)) == 1


def test_a_legacy_entry_without_a_run_id_still_counts_as_in_flight(
    store: Store, node: Node
) -> None:
    with closing(sqlite3.connect(store.path)) as connection:
        insert_legacy_sq_run_entry(
            connection,
            entry_id=LEGACY_ENTRY_ID,
            project_id=PROJECT,
            node_id=node.id,
            parameters={PARAM_PIPELINE: "p5", PARAM_PARAMS: {}},
            issued_at="2026-10-15T22:00:00+00:00",
        )

    _escalate(store, _in(node.id))  # must not raise KeyError

    assert store.blocked_state_for(node.id) is None
    [row] = store.open_project_escalations(PROJECT)
    assert row.payload is not None and row.payload["run_ids"] == [LEGACY_ENTRY_ID]


# -- the plan-read vocabulary (slice 123, D8) -----------------------------------


@pytest.mark.parametrize(
    ("member", "value"),
    [
        (FaultKind.PLAN_READ_FAILED, "plan_read_failed"),
        (FaultKind.LIFECYCLE_ORPHAN, "lifecycle_orphan"),
        (FaultKind.PLAN_STATUS_UNKNOWN, "plan_status_unknown"),
    ],
)
def test_the_new_fault_kinds_have_their_exact_values(
    member: FaultKind, value: str
) -> None:
    assert member.value == value
    assert FaultKind(value) is member


@pytest.mark.parametrize(
    ("constant", "value"),
    [
        (faults.PAYLOAD_FAULT_KIND, "fault_kind"),
        (faults.PAYLOAD_CF_PROJECT_ID, "cf_project_id"),
        (faults.PAYLOAD_INDEX, "index"),
        (faults.PAYLOAD_FORMER_INDEX, "former_index"),
        (faults.PAYLOAD_FORMER_SLICE_NAME, "former_slice_name"),
        (faults.PAYLOAD_STATUS, "status"),
    ],
)
def test_the_lifecycle_payload_keys_have_their_exact_values(
    constant: str, value: str
) -> None:
    assert constant == value


def test_a_plan_read_failed_fault_raises_one_project_escalation(
    store: Store,
) -> None:
    tick = TickFaults()
    tick.add(Fault(FaultKind.PLAN_READ_FAILED, "cf list initiatives exited 1"))

    wrote_first = raise_expected_faults(store, PROJECT, tick)
    wrote_again = raise_expected_faults(store, PROJECT, tick)

    [row] = store.open_project_escalations(PROJECT)
    assert row.fault_kind == "plan_read_failed"
    assert wrote_first and not wrote_again


def test_an_extra_key_that_would_shadow_a_standard_key_raises(store: Store) -> None:
    tick = TickFaults()
    tick.add(
        Fault(
            FaultKind.PLAN_READ_FAILED,
            "cf list initiatives exited 1",
            extra={faults.PAYLOAD_DETAIL: "shadowed"},
        )
    )

    with pytest.raises(ValueError, match=faults.PAYLOAD_DETAIL):
        raise_expected_faults(store, PROJECT, tick)
    assert store.open_project_escalations(PROJECT) == []
