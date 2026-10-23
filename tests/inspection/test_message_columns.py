"""``messages`` rows carry outcome, fault kind and closure columns (slice 121)."""

from __future__ import annotations

from routing_helpers import submit_intent

from amoeba.inspection import LISTINGS_BY_NAME, ListingRequest
from amoeba.inspection.inbox import CHANNEL_OPTION, message_rows
from amoeba.store import AcknowledgmentOutcome, Store

PROJECT = "demo"
NEW_COLUMNS = (
    "acknowledgment_outcome",
    "acknowledgment_reason",
    "fault_kind",
    "closed_at",
)


def _rows(store: Store) -> list[dict[str, object]]:
    request = ListingRequest(
        project_id=PROJECT, options={CHANNEL_OPTION.name: None}, compact=False
    )
    return [dict(row) for row in message_rows(store, request)]


def test_an_acknowledged_intent_shows_its_outcome_and_reason(store: Store) -> None:
    intent_id = submit_intent(store, "s-1")
    store.acknowledge_message(
        intent_id,
        acknowledged_by="runner",
        outcome=AcknowledgmentOutcome.NO_OP,
        reason="already held",
    )

    [row] = _rows(store)

    assert row["acknowledgment_outcome"] == "no_op"
    assert row["acknowledgment_reason"] == "already held"
    assert row["acknowledged_at"] != ""


def test_an_unacknowledged_intent_shows_empty_strings(store: Store) -> None:
    submit_intent(store, "s-1")

    [row] = _rows(store)

    assert [row[column] for column in NEW_COLUMNS] == ["", "", "", ""]


def test_a_project_escalation_shows_its_fault_kind_until_closed(store: Store) -> None:
    opened = store.raise_project_escalation(
        PROJECT, fault_kind="plan_read_failed", payload={"error": "boom"}
    )

    [row] = _rows(store)
    assert row["fault_kind"] == "plan_read_failed"
    assert row["closed_at"] == ""
    assert row["node_id"] == "" and row["blocked_state_id"] == ""

    store.close_project_escalation(opened.id, closed_by="runner")

    [closed] = _rows(store)
    assert closed["closed_at"] != ""


def test_the_listing_declares_the_new_columns() -> None:
    assert set(NEW_COLUMNS) <= set(LISTINGS_BY_NAME["messages"].columns)
