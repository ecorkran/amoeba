"""Rows for the detection listings: ``watches`` and ``detections``.

A sibling of ``inspect.py``, which registers these in its one ``LISTINGS``
registry. Both receive a **read-only** store and write nothing. A watch's state
is computed on read, from the directory and the journal, so it needs no tenant
memory and is right whether or not the process is running.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Final

from amoeba.inspection.listing import ChoiceOption, ListingRequest, Row
from amoeba.process.review_sources import (
    ReviewDirectoryUnavailableError,
    list_review_files,
)
from amoeba.store import DetectionOutcome, ReviewWatch, Store


class WatchState(StrEnum):
    """What ``inspect watches`` reports for one watch (LLD "Watch states")."""

    INACTIVE = "inactive"
    UNREACHABLE = "unreachable"
    BASELINE_PENDING = "baseline_pending"
    DEFERRED = "deferred"
    OK = "ok"


WATCH_COLUMNS: Final = (
    "reviews_dir",
    "active",
    "registered_at",
    "baselined_at",
    "state",
)

DETECTION_COLUMNS: Final = (
    "detected_at",
    "outcome",
    "path",
    "node_id",
    "verdict_id",
    "record_id",
    "recorded_since",
    "detail",
)

#: The ``--outcome`` choices, from the one definition.
OUTCOME_CHOICES: Final = tuple(outcome.value for outcome in DetectionOutcome)

OUTCOME_OPTION = ChoiceOption(
    name="outcome",
    help_text="Only this outcome. Every outcome when omitted.",
    choices=OUTCOME_CHOICES,
)


def _reachable(directory: str) -> bool:
    try:
        list_review_files(Path(directory))
    except ReviewDirectoryUnavailableError:
        # Specific: the state this listing exists to show.
        return False
    return True


def watch_state(store: Store, watch: ReviewWatch) -> WatchState:
    """Inactive first; then unreachable, baseline pending, deferred, ok."""
    if not watch.active:
        return WatchState.INACTIVE
    if not _reachable(watch.reviews_dir):
        return WatchState.UNREACHABLE
    if watch.baselined_at is None:
        return WatchState.BASELINE_PENDING
    if store.has_unresolved_review_entry(watch.project_id):
        return WatchState.DEFERRED
    return WatchState.OK


def watch_rows(store: Store, request: ListingRequest) -> list[Row]:
    """Every registered review directory and its computed state."""
    return [
        {
            "reviews_dir": watch.reviews_dir,
            "active": watch.active,
            "registered_at": watch.registered_at.isoformat(),
            "baselined_at": (
                watch.baselined_at.isoformat() if watch.baselined_at else ""
            ),
            "state": watch_state(store, watch).value,
        }
        for watch in store.watches(request.require_project_id())
    ]


def detection_rows(store: Store, request: ListingRequest) -> list[Row]:
    """The detection ledger in detection order, optionally one outcome."""
    outcome_value = request.option(OUTCOME_OPTION)
    outcome = None if outcome_value is None else DetectionOutcome(outcome_value)
    return [
        {
            "detected_at": detection.detected_at.isoformat(),
            "outcome": detection.outcome.value,
            "path": detection.path,
            "node_id": detection.node_id or "",
            "verdict_id": detection.verdict_id or "",
            "record_id": detection.record_id or "",
            "recorded_since": (
                detection.record_id is not None
                and store.recorded_since(
                    request.require_project_id(), detection.record_id
                )
            ),
            "detail": detection.detail or "",
        }
        for detection in store.detections(request.require_project_id(), outcome=outcome)
    ]
