"""Feed row mapping: valid rows map; unknown values raise, never default."""

from __future__ import annotations

import pytest

from amoeba.store.feed_models import ChangeKind, DetectionOutcome
from amoeba.store.mapping_feed import map_change, map_detected_review, map_watch
from amoeba.store.models import UnknownVocabularyValueError

AT = "2026-10-15T00:00:00+00:00"

CHANGE_ROW = (
    7,
    "demo",
    "node_status_changed",
    "n-1",
    "n-1",
    '{"from": "runnable", "to": "done"}',
    AT,
)
WATCH_ROW = ("demo", "/abs/reviews", 1, AT, None, AT)
DETECTION_ROW = (
    3,
    "demo",
    "/abs/r.md",
    "abc",
    "ingested",
    "n-1",
    "v-1",
    "v-1",
    None,
    AT,
)


def test_a_change_row_maps() -> None:
    change = map_change(CHANGE_ROW)
    assert change.seq == 7
    assert change.kind is ChangeKind.NODE_STATUS_CHANGED
    assert change.payload == {"from": "runnable", "to": "done"}
    assert change.recorded_at.isoformat() == AT


def test_a_watch_row_maps() -> None:
    watch = map_watch(WATCH_ROW)
    assert watch.active is True
    assert watch.baselined_at is None


def test_a_detection_row_maps() -> None:
    detection = map_detected_review(DETECTION_ROW)
    assert detection.outcome is DetectionOutcome.INGESTED
    assert detection.verdict_id == "v-1"
    assert detection.detail is None


def test_an_unknown_kind_raises() -> None:
    row = (*CHANGE_ROW[:2], "node_vanished", *CHANGE_ROW[3:])
    with pytest.raises(UnknownVocabularyValueError, match="kind"):
        map_change(row)


def test_an_unknown_outcome_raises() -> None:
    row = (*DETECTION_ROW[:4], "guessed", *DETECTION_ROW[5:])
    with pytest.raises(UnknownVocabularyValueError, match="outcome"):
        map_detected_review(row)


@pytest.mark.parametrize("payload", ["not json", "[1, 2]", "null"])
def test_a_malformed_payload_raises_rather_than_returning_empty(payload: str) -> None:
    row = (*CHANGE_ROW[:5], payload, CHANGE_ROW[6])
    with pytest.raises(UnknownVocabularyValueError, match="payload"):
        map_change(row)


def test_an_active_flag_outside_zero_and_one_raises() -> None:
    row = (*WATCH_ROW[:2], 2, *WATCH_ROW[3:])
    with pytest.raises(UnknownVocabularyValueError, match="active"):
        map_watch(row)
