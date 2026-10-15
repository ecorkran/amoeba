"""``record_detected_verdict``: one transaction for a verdict and its ledger row."""

from __future__ import annotations

import pytest
from evidence_harness import PROJECT, seed_node, verdict_input
from feed_harness import raw_changes

from amoeba.store import (
    ChangeKind,
    DetectionInput,
    DetectionOutcome,
    Store,
    StoreError,
    sql_feed,
)


def _detection(
    path: str = "/r/a.md",
    digest: str = "d1",
    outcome: DetectionOutcome = DetectionOutcome.INGESTED,
) -> DetectionInput:
    return DetectionInput(
        project_id=PROJECT, path=path, digest=digest, outcome=outcome, record_id="v-1"
    )


def test_success_writes_one_verdict_and_one_ingested_row(store: Store) -> None:
    node_id = seed_node(store)
    record, detected = store.record_detected_verdict(
        verdict_input("v-1", node_id), _detection()
    )

    assert store.verdicts(PROJECT) == [record]
    assert store.detections(PROJECT) == [detected]
    assert (detected.outcome, detected.verdict_id, detected.node_id) == (
        DetectionOutcome.INGESTED,
        "v-1",
        node_id,
    )
    kinds = [c.kind for c in raw_changes(store, PROJECT)]
    assert kinds[-2:] == [ChangeKind.VERDICT_RECORDED, ChangeKind.REVIEW_DETECTED]


@pytest.mark.parametrize(
    "outcome", [o for o in DetectionOutcome if o is not DetectionOutcome.INGESTED]
)
def test_another_outcome_raises_and_writes_nothing(
    store: Store, outcome: DetectionOutcome
) -> None:
    node_id = seed_node(store)
    with pytest.raises(ValueError, match="ingested"):
        store.record_detected_verdict(
            verdict_input("v-1", node_id), _detection(outcome=outcome)
        )
    assert store.verdicts(PROJECT) == []
    assert store.detections(PROJECT) == []


def test_a_failed_ledger_insert_rolls_back_the_verdict(store: Store) -> None:
    node_id = seed_node(store)
    changes_before = len(raw_changes(store, PROJECT))
    # A TEMP trigger is per connection, so it goes on the store's own.
    store._connection.execute(  # pyright: ignore[reportPrivateUsage]
        f"CREATE TEMP TRIGGER refuse BEFORE INSERT ON "
        f"{sql_feed.TABLE_DETECTED_REVIEWS} "
        "BEGIN SELECT RAISE(ABORT, 'refused'); END"
    )

    with pytest.raises(StoreError):
        store.record_detected_verdict(verdict_input("v-1", node_id), _detection())

    assert store.verdicts(PROJECT) == []
    assert store.detections(PROJECT) == []
    assert len(raw_changes(store, PROJECT)) == changes_before


def test_a_hand_edit_points_a_new_row_at_the_existing_verdict(store: Store) -> None:
    node_id = seed_node(store)
    verdict = verdict_input("v-1", node_id)
    store.record_detected_verdict(verdict, _detection(digest="original"))
    changes_before = len(raw_changes(store, PROJECT))

    record, detected = store.record_detected_verdict(
        verdict, _detection(digest="edited")
    )

    assert [v.id for v in store.verdicts(PROJECT)] == ["v-1"]
    assert detected.verdict_id == record.id == "v-1"
    assert len(store.detections(PROJECT)) == 2
    new = raw_changes(store, PROJECT)[changes_before:]
    assert [c.kind for c in new] == [ChangeKind.REVIEW_DETECTED]


def test_an_existing_ledger_key_surfaces_the_integrity_error(store: Store) -> None:
    node_id = seed_node(store)
    store.record_detected_verdict(verdict_input("v-1", node_id), _detection())
    with pytest.raises(StoreError):
        store.record_detected_verdict(verdict_input("v-1", node_id), _detection())
