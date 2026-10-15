"""Shared rig for driving ``ReviewDetectionTenant`` in-process.

Real stores through ``LocalHost``, a fake clock, real review fixtures copied
into a ``tmp_path`` directory. Helpers hold no detection assertions.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from local_host_harness import LocalHost

from amoeba.process.review_detection import ReviewDetectionTenant
from amoeba.process.review_sources import DirectoryReviewSource, ReviewSource
from amoeba.store import (
    CFReference,
    NodeKind,
    Store,
    SubmissionKind,
    SubmissionOutcome,
)
from amoeba.store.inbox_models import WATCH_ACTIVE, WATCH_REVIEWS_DIR

PROJECT = "demo"
SLICE_NAME = "resident-process-and-recovery"
LABEL = "sq-test-label 0.0.0"
FIXTURES = Path(__file__).parent / "fixtures" / "sq_reviews"

#: Real fixtures for the slice above (see the task file's fixture list).
ROUND_ONE_PART_ONE = (
    "102-review.tasks.resident-process-and-recovery.part-1.20260921T112529.md"
)
ROUND_ONE_PART_TWO = (
    "102-review.tasks.resident-process-and-recovery.part-2.20260921T112635.md"
)
ROUND_TWO_PART_ONE = "102-review.tasks.resident-process-and-recovery.part-1.md"
PROVIDER_FAILURE = "102-review.tasks.resident-process-and-recovery.part-2.md"
STAMPED = "105-review.slice.squadron-review-parser-and-ingest.20261015T041112.md"

SUBMITTED_AT = datetime(2026, 10, 15, tzinfo=UTC)


class FakeClock:
    """Monotonic seconds that move only when told to."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class DetectionRig:
    """One project, one slice node, one reviews directory, one tenant."""

    def __init__(
        self,
        host: LocalHost,
        reviews_dir: Path,
        *,
        label: str = LABEL,
        source_factory: Callable[[Path], ReviewSource] = DirectoryReviewSource,
    ) -> None:
        self.host = host
        self.reviews_dir = reviews_dir
        self.clock = FakeClock()
        self.store: Store = host.open_project(PROJECT)
        self.tenant = self.new_tenant(label=label, source_factory=source_factory)
        self._submissions = 0

    def new_tenant(
        self,
        *,
        label: str = LABEL,
        source_factory: Callable[[Path], ReviewSource] = DirectoryReviewSource,
    ) -> ReviewDetectionTenant:
        """A fresh tenant over the same store: what a restart builds."""
        return ReviewDetectionTenant(
            version_label=label, source_factory=source_factory, clock=self.clock
        )

    def seed_slice_node(self, slice_name: str = SLICE_NAME) -> str:
        return self.store.create_node(
            project_id=PROJECT,
            kind=NodeKind.SLICE,
            title=slice_name,
            cf=CFReference(slice_name=slice_name),
        ).id

    def watch(self, *, active: bool = True) -> None:
        """Register or toggle the watch through the real inbox apply."""
        self._submissions += 1
        record = self.store.apply_submission(
            submission_id=f"watch-{self._submissions}",
            project_id=PROJECT,
            kind=SubmissionKind.WATCH_REVIEWS,
            submitted_by="pm",
            submitted_at=SUBMITTED_AT,
            payload={WATCH_REVIEWS_DIR: str(self.reviews_dir), WATCH_ACTIVE: active},
        )
        assert record.outcome is SubmissionOutcome.APPLIED, record.reason

    def copy(self, name: str, as_name: str | None = None) -> Path:
        """Copy a real fixture into the reviews directory."""
        return Path(shutil.copy(FIXTURES / name, self.reviews_dir / (as_name or name)))

    def run_scans(self, count: int = 1) -> bool:
        """Advance past the scan interval before each tick; whether any worked."""
        interval = self.host.settings.review_scan_interval_seconds
        worked = False
        for _ in range(count):
            self.clock.now += interval + 1
            worked = self.tenant.tick(self.host) or worked
        return worked
