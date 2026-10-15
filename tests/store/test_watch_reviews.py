"""The ``watch_reviews`` kind: registering, deactivating, and replay."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest
from feed_harness import apply

from amoeba.inbox.envelope import EnvelopeError, build_envelope
from amoeba.store import (
    QuarantineReason,
    Store,
    SubmissionKind,
    SubmissionOutcome,
    sql_feed,
)
from amoeba.store.inbox_models import WATCH_ACTIVE, WATCH_REVIEWS_DIR

PROJECT = "demo"
REVIEWS_DIR = "/abs/project/reviews"
STAGED_BASELINE = "2026-10-15T00:00:00+00:00"
SUBMITTED_AT = datetime(2026, 10, 15, tzinfo=UTC)


def _watch(store: Store, submission_id: str, *, active: bool) -> None:
    payload = {WATCH_REVIEWS_DIR: REVIEWS_DIR, WATCH_ACTIVE: active}
    record = apply(store, submission_id, SubmissionKind.WATCH_REVIEWS, payload, PROJECT)
    assert record.outcome is SubmissionOutcome.APPLIED, record.reason


def _raw_watches(store: Store) -> list[tuple[object, ...]]:
    columns = ", ".join(sql_feed.WATCH_COLUMNS)
    with sqlite3.connect(store.path) as connection:
        return connection.execute(
            f"SELECT {columns} FROM {sql_feed.TABLE_REVIEW_WATCHES}"
        ).fetchall()


def _stage_baseline(store: Store) -> None:
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            f"UPDATE {sql_feed.TABLE_REVIEW_WATCHES} "
            f"SET {sql_feed.COL_WATCH_BASELINED_AT} = ?",
            (STAGED_BASELINE,),
        )


def test_registering_creates_a_watch_with_no_baseline(store: Store) -> None:
    _watch(store, "s-1", active=True)
    [(project, reviews_dir, active, registered, baselined, updated)] = _raw_watches(
        store
    )
    assert (project, reviews_dir, active, baselined) == (
        PROJECT,
        REVIEWS_DIR,
        1,
        None,
    )
    assert registered == updated


def test_deactivate_then_reactivate_keeps_the_baseline(store: Store) -> None:
    _watch(store, "s-1", active=True)
    _stage_baseline(store)
    _watch(store, "s-2", active=False)
    assert _raw_watches(store)[0][2] == 0
    _watch(store, "s-3", active=True)

    [row] = _raw_watches(store)
    assert row[2] == 1
    assert row[4] == STAGED_BASELINE


def test_a_replayed_submission_is_a_no_op(store: Store) -> None:
    _watch(store, "s-1", active=True)
    before = _raw_watches(store)
    _watch(store, "s-1", active=False)
    assert _raw_watches(store) == before


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
