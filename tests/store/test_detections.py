"""The detection ledger: idempotent records, filtered reads, ``recorded_since``."""

from __future__ import annotations

import pytest
from evidence_harness import PROJECT, seed_node, verdict_input
from feed_harness import apply

from amoeba.store import (
    DetectionInput,
    DetectionOutcome,
    Store,
    SubmissionKind,
    SubmissionOutcome,
)


def _detection(
    path: str, outcome: DetectionOutcome, digest: str = "d1", **fields: str
) -> DetectionInput:
    return DetectionInput(
        project_id=PROJECT, path=path, digest=digest, outcome=outcome, **fields
    )


@pytest.mark.parametrize("outcome", list(DetectionOutcome))
def test_each_outcome_records(store: Store, outcome: DetectionOutcome) -> None:
    recorded = store.record_detection(_detection("/r/a.md", outcome, detail="why"))
    assert (recorded.outcome, recorded.path, recorded.detail) == (
        outcome,
        "/r/a.md",
        "why",
    )
    assert store.detections(PROJECT) == [recorded]


def test_a_repeated_key_returns_the_first_row_and_inserts_nothing(
    store: Store,
) -> None:
    first = store.record_detection(_detection("/r/a.md", DetectionOutcome.UNPARSEABLE))
    again = store.record_detection(_detection("/r/a.md", DetectionOutcome.INGESTED))
    assert again == first
    assert len(store.detections(PROJECT)) == 1


def test_a_new_digest_on_the_same_path_is_a_new_row(store: Store) -> None:
    store.record_detection(_detection("/r/a.md", DetectionOutcome.UNPARSEABLE))
    store.record_detection(
        _detection("/r/a.md", DetectionOutcome.UNPARSEABLE, digest="d2")
    )
    assert len(store.detections(PROJECT)) == 2


def test_detections_filter_by_outcome_in_detection_order(store: Store) -> None:
    for name, outcome in (
        ("a", DetectionOutcome.UNATTRIBUTED),
        ("b", DetectionOutcome.UNPARSEABLE),
        ("c", DetectionOutcome.UNATTRIBUTED),
    ):
        store.record_detection(_detection(f"/r/{name}.md", outcome))

    unattributed = store.detections(PROJECT, outcome=DetectionOutcome.UNATTRIBUTED)
    assert [d.path for d in unattributed] == ["/r/a.md", "/r/c.md"]
    assert [d.id for d in store.detections(PROJECT)] == sorted(
        d.id for d in store.detections(PROJECT)
    )


def test_recorded_since_turns_true_after_a_direct_record(store: Store) -> None:
    node_id = seed_node(store)
    assert store.recorded_since(PROJECT, "rec-1") is False
    store.record_verdict(verdict_input("rec-1", node_id), project_id=PROJECT)
    assert store.recorded_since(PROJECT, "rec-1") is True


def test_recorded_since_sees_a_verdict_applied_through_the_inbox(
    store: Store,
) -> None:
    node_id = seed_node(store)
    payload: dict[str, object] = {
        "node_id": node_id,
        "verdict": "CONCERNS",
        "derivation": "stated",
        "fallback_used": None,
        "findings_parsed": True,
        "provider_failure": False,
        "review_type": "tasks",
        "model": "m",
        "findings": [],
        "upstream": "squadron",
        "upstream_version": "0.14.0",
        "source": "artifact_frontmatter",
    }
    record = apply(store, "rec-1", SubmissionKind.VERDICT, payload, PROJECT)
    assert record.outcome is SubmissionOutcome.APPLIED, record.reason
    assert store.recorded_since(PROJECT, "rec-1") is True


def test_a_verdict_under_another_id_leaves_recorded_since_false(
    store: Store,
) -> None:
    node_id = seed_node(store)
    store.record_verdict(verdict_input("override", node_id), project_id=PROJECT)
    assert store.recorded_since(PROJECT, "rec-1") is False
