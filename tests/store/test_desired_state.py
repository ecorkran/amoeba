"""D3 and D8: desired state is written inside the intent's acknowledgment."""

from __future__ import annotations

from pathlib import Path

import pytest
from fault_injection import InjectedFailureError, fail_on_statement
from routing_helpers import make_node, submit_intent

from amoeba.store import (
    AcknowledgmentOutcome,
    ClearDesiredState,
    InvalidTransitionError,
    NodeNotFoundError,
    SetDesiredState,
    Store,
    sql_runner,
)

PROJECT = "demo"
APPLIED = AcknowledgmentOutcome.APPLIED


def _ack(
    store: Store,
    intent_id: str,
    change: SetDesiredState | ClearDesiredState | None,
    outcome: AcknowledgmentOutcome = APPLIED,
) -> None:
    store.acknowledge_message(
        intent_id,
        acknowledged_by="runner",
        outcome=outcome,
        reason="r" if outcome is AcknowledgmentOutcome.REJECTED else None,
        desired_state=change,
    )


def test_reads_are_empty_on_a_fresh_store(store: Store) -> None:
    assert store.desired_state(PROJECT) is None
    assert store.desired_state(PROJECT, node_id="n") is None
    assert store.desired_states(PROJECT) == []


def test_set_at_the_project_target_and_a_node_target(store: Store) -> None:
    node_id = make_node(store)
    first = submit_intent(store, "sub-1")
    second = submit_intent(store, "sub-2")

    _ack(store, first, SetDesiredState(drive=True, drive_until_step="P5"))
    _ack(store, second, SetDesiredState(node_id=node_id, hold=True))

    project_row = store.desired_state(PROJECT)
    node_row = store.desired_state(PROJECT, node_id=node_id)
    assert project_row is not None and node_row is not None
    assert (project_row.drive, project_row.drive_until_step, project_row.hold) == (
        True,
        "P5",
        None,
    )
    assert project_row.message_id == first
    assert (node_row.drive, node_row.hold, node_row.message_id) == (None, True, second)
    assert store.desired_states(PROJECT) == [project_row, node_row]


def test_setting_a_target_again_replaces_the_whole_row(store: Store) -> None:
    first = submit_intent(store, "sub-1")
    second = submit_intent(store, "sub-2")
    _ack(store, first, SetDesiredState(hold=True))
    _ack(store, second, SetDesiredState(drive=True))

    row = store.desired_state(PROJECT)
    assert row is not None
    assert (row.drive, row.hold, row.message_id) == (True, None, second)
    assert len(store.desired_states(PROJECT)) == 1


def test_clear_deletes_the_row(store: Store) -> None:
    node_id = make_node(store)
    _ack(store, submit_intent(store, "s1"), SetDesiredState(node_id=node_id, hold=True))
    _ack(store, submit_intent(store, "s2"), ClearDesiredState(node_id=node_id))

    assert store.desired_state(PROJECT, node_id=node_id) is None


def test_clearing_a_target_with_no_row_acknowledges_and_writes_nothing(
    store: Store,
) -> None:
    intent_id = submit_intent(store)
    _ack(store, intent_id, ClearDesiredState())

    assert store.pending_intents(PROJECT) == []
    assert store.desired_states(PROJECT) == []


@pytest.mark.parametrize(
    "change",
    [
        SetDesiredState(),
        SetDesiredState(drive_until_step="P5"),
        SetDesiredState(drive=False, drive_until_step="P5"),
        SetDesiredState(hold=True, drive_until_step="P5"),
        SetDesiredState(drive=True, drive_until_step=""),
        SetDesiredState(drive=True, drive_until_step="  "),
    ],
)
def test_a_shape_violation_raises_and_leaves_the_intent_pending(
    store: Store, change: SetDesiredState
) -> None:
    intent_id = submit_intent(store)

    with pytest.raises(ValueError):
        _ack(store, intent_id, change)

    assert [m.id for m in store.pending_intents(PROJECT)] == [intent_id]
    assert store.desired_states(PROJECT) == []


def test_a_node_in_another_project_or_missing_is_refused(store: Store) -> None:
    other = make_node(store, "other")
    intent_id = submit_intent(store)

    for node_id in (other, "no-such-node"):
        with pytest.raises(NodeNotFoundError):
            _ack(store, intent_id, SetDesiredState(node_id=node_id, hold=True))
        with pytest.raises(NodeNotFoundError):
            _ack(store, intent_id, ClearDesiredState(node_id=node_id))

    assert [m.id for m in store.pending_intents(PROJECT)] == [intent_id]
    assert store.desired_states(PROJECT) == []


@pytest.mark.parametrize(
    "outcome", [AcknowledgmentOutcome.NO_OP, AcknowledgmentOutcome.REJECTED]
)
def test_a_desired_state_needs_the_applied_outcome(
    store: Store, outcome: AcknowledgmentOutcome
) -> None:
    intent_id = submit_intent(store)

    with pytest.raises(ValueError, match="applied"):
        _ack(store, intent_id, SetDesiredState(hold=True), outcome)

    assert [m.id for m in store.pending_intents(PROJECT)] == [intent_id]


def test_a_failed_desired_state_write_rolls_the_acknowledgment_back(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    intent_id = submit_intent(store)
    fail_on_statement(monkeypatch, store, sql_runner.INSERT_DESIRED_STATE)

    with pytest.raises(InjectedFailureError):
        _ack(store, intent_id, SetDesiredState(hold=True))

    assert [m.id for m in store.pending_intents(PROJECT)] == [intent_id]
    assert store.desired_states(PROJECT) == []


def test_a_desired_state_on_an_acknowledged_intent_changes_nothing(
    store: Store,
) -> None:
    first = submit_intent(store)
    _ack(store, first, SetDesiredState(hold=True))
    before = store.desired_state(PROJECT)

    with pytest.raises(InvalidTransitionError):
        _ack(store, first, SetDesiredState(drive=True))

    assert store.desired_state(PROJECT) == before


def test_a_node_target_is_not_read_through_another_project(store: Store) -> None:
    node_id = make_node(store)
    _ack(store, submit_intent(store, "s1"), SetDesiredState(node_id=node_id, hold=True))

    assert store.desired_state(PROJECT, node_id=node_id) is not None
    assert store.desired_state("other", node_id=node_id) is None


def test_reads_work_through_a_read_only_handle(store_file: Path) -> None:
    with Store.open(store_file) as store:
        _ack(store, submit_intent(store), SetDesiredState(hold=True))
        expected = store.desired_states(PROJECT)

    with Store.open_read_only(store_file) as reader:
        assert reader.desired_states(PROJECT) == expected
        assert reader.desired_state(PROJECT) == expected[0]
