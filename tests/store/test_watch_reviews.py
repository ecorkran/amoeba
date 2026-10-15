"""The ``watch_reviews`` kind, the ``watches`` read, and the atomic baseline."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from feed_harness import apply, raw_changes

from amoeba.inbox.envelope import EnvelopeError, build_envelope
from amoeba.store import (
    BaselineEntry,
    DetectionOutcome,
    QuarantineReason,
    ReviewWatch,
    Store,
    StoreError,
    SubmissionKind,
    SubmissionOutcome,
    sql_feed,
)
from amoeba.store.inbox_models import WATCH_ACTIVE, WATCH_REVIEWS_DIR

PROJECT = "demo"
REVIEWS_DIR = "/abs/project/reviews"
SUBMITTED_AT = datetime(2026, 10, 15, tzinfo=UTC)
ENTRIES = (
    BaselineEntry("/abs/project/reviews/a.md", "da"),
    BaselineEntry("/abs/project/reviews/b.md", "db"),
)


def _watch(store: Store, submission_id: str, *, active: bool) -> None:
    payload = {WATCH_REVIEWS_DIR: REVIEWS_DIR, WATCH_ACTIVE: active}
    record = apply(store, submission_id, SubmissionKind.WATCH_REVIEWS, payload, PROJECT)
    assert record.outcome is SubmissionOutcome.APPLIED, record.reason


def _only_watch(store: Store) -> ReviewWatch:
    [watch] = store.watches(PROJECT)
    return watch


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


def test_registering_creates_a_watch_with_no_baseline(store: Store) -> None:
    _watch(store, "s-1", active=True)
    watch = _only_watch(store)
    assert (watch.project_id, watch.reviews_dir, watch.active) == (
        PROJECT,
        REVIEWS_DIR,
        True,
    )
    assert watch.baselined_at is None
    assert watch.registered_at == watch.updated_at


def test_deactivate_then_reactivate_keeps_the_baseline(store: Store) -> None:
    _watch(store, "s-1", active=True)
    store.baseline_watch(PROJECT, REVIEWS_DIR, ())
    baselined_at = _only_watch(store).baselined_at
    _watch(store, "s-2", active=False)
    assert _only_watch(store).active is False
    _watch(store, "s-3", active=True)

    watch = _only_watch(store)
    assert watch.active is True
    assert watch.baselined_at == baselined_at is not None


def test_a_replayed_submission_is_a_no_op(store: Store) -> None:
    _watch(store, "s-1", active=True)
    before = store.watches(PROJECT)
    _watch(store, "s-1", active=False)
    assert store.watches(PROJECT) == before


def test_a_relative_path_is_quarantined_as_invalid() -> None:
    with pytest.raises(EnvelopeError) as raised:
        build_envelope(
            submission_id="s-1",
            project_id=PROJECT,
            kind=SubmissionKind.WATCH_REVIEWS,
            submitted_by="pm",
            submitted_at=SUBMITTED_AT,
            payload={WATCH_REVIEWS_DIR: "reviews", WATCH_ACTIVE: True},
        )
    assert raised.value.reason is QuarantineReason.INVALID_PAYLOAD


# --------------------------------------------------------------------------
# The baseline
# --------------------------------------------------------------------------


def test_baseline_writes_one_row_per_entry_and_sets_baselined_at(
    store: Store,
) -> None:
    _watch(store, "s-1", active=True)
    store.baseline_watch(PROJECT, REVIEWS_DIR, ENTRIES)

    rows = store.detections(PROJECT)
    assert [(d.path, d.digest, d.outcome) for d in rows] == [
        (entry.path, entry.digest, DetectionOutcome.BASELINE) for entry in ENTRIES
    ]
    assert _only_watch(store).baselined_at is not None


def test_baseline_emits_no_change(store: Store) -> None:
    _watch(store, "s-1", active=True)
    store.baseline_watch(PROJECT, REVIEWS_DIR, ENTRIES)
    assert raw_changes(store, PROJECT) == []


def test_an_entry_already_in_the_ledger_is_skipped(store: Store) -> None:
    _watch(store, "s-1", active=True)
    store.baseline_watch(PROJECT, REVIEWS_DIR, (*ENTRIES, ENTRIES[0]))
    assert len(store.detections(PROJECT)) == len(ENTRIES)


def test_an_unregistered_directory_raises_and_writes_nothing(store: Store) -> None:
    with pytest.raises(StoreError):
        store.baseline_watch(PROJECT, REVIEWS_DIR, ENTRIES)
    assert store.detections(PROJECT) == []


def test_a_second_baseline_raises_and_writes_nothing(store: Store) -> None:
    _watch(store, "s-1", active=True)
    store.baseline_watch(PROJECT, REVIEWS_DIR, ())
    with pytest.raises(StoreError):
        store.baseline_watch(PROJECT, REVIEWS_DIR, ENTRIES)
    assert store.detections(PROJECT) == []


def test_a_failed_insert_rolls_back_the_whole_baseline(store: Store) -> None:
    _watch(store, "s-1", active=True)
    # A TEMP trigger is per connection, so it goes on the store's own.
    store._connection.execute(  # pyright: ignore[reportPrivateUsage]
        f"CREATE TEMP TRIGGER refuse_b BEFORE INSERT ON "
        f"{sql_feed.TABLE_DETECTED_REVIEWS} "
        f"WHEN new.{sql_feed.COL_DETECTION_PATH} = '{ENTRIES[1].path}' "
        "BEGIN SELECT RAISE(ABORT, 'refused'); END"
    )

    with pytest.raises(StoreError):
        store.baseline_watch(PROJECT, REVIEWS_DIR, ENTRIES)

    assert store.detections(PROJECT) == []
    assert _only_watch(store).baselined_at is None
