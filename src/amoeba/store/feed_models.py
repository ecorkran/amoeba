"""Closed vocabularies and transfer objects for the change feed and detection.

Every change kind and detection outcome is defined here and nowhere else in
Python. Migration ``006`` repeats the values as literals inside its emission
triggers (a shipped migration is frozen); the invariant test ties the two
together. Like ``models.py``, this module knows nothing about SQL or
``sqlite3``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final


class ChangeKind(StrEnum):
    """What a row in the change log announces."""

    NODE_CREATED = "node_created"
    NODE_STATUS_CHANGED = "node_status_changed"
    VERDICT_RECORDED = "verdict_recorded"
    MESSAGE_POSTED = "message_posted"
    REVIEW_DETECTED = "review_detected"
    CHECK_RECORDED = "check_recorded"


class DetectionOutcome(StrEnum):
    """What detection did with one ``(path, digest)``."""

    BASELINE = "baseline"
    INGESTED = "ingested"
    UNATTRIBUTED = "unattributed"
    UNPARSEABLE = "unparseable"
    RUNNER_ISSUED = "runner_issued"


#: Outcomes recorded in the ledger that emit no change (D8): a baseline row is
#: a file that existed before registration, and a ``runner_issued`` row marks a
#: review the Runner already announced through its own verdict.
SILENT_OUTCOMES: Final = frozenset(
    {DetectionOutcome.BASELINE, DetectionOutcome.RUNNER_ISSUED}
)


@dataclass(frozen=True)
class Change:
    """One entry in a project's change log. ``seq`` is the subscriber's cursor."""

    seq: int
    project_id: str
    kind: ChangeKind
    node_id: str | None
    subject_id: str
    payload: Mapping[str, object]
    recorded_at: datetime


@dataclass(frozen=True)
class ReviewWatch:
    """A registered review directory. Detection scans it only once baselined."""

    project_id: str
    reviews_dir: str
    active: bool
    registered_at: datetime
    baselined_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True)
class DetectedReview:
    """One ledger row: a ``(path, digest)`` detection has examined."""

    id: int
    project_id: str
    path: str
    digest: str
    outcome: DetectionOutcome
    node_id: str | None
    verdict_id: str | None
    record_id: str | None
    detail: str | None
    detected_at: datetime


@dataclass(frozen=True)
class DetectionInput:
    """What a caller records about one examined file.

    ``record_id`` is 105's parsed-content id, set for every file that parsed.
    """

    project_id: str
    path: str
    digest: str
    outcome: DetectionOutcome
    node_id: str | None = None
    verdict_id: str | None = None
    record_id: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class BaselineEntry:
    """One file present when a watch was baselined."""

    path: str
    digest: str
