"""``ReviewDetectionTenant`` — notices reviews nobody in Amoeba launched.

Once per ``review_scan_interval_seconds`` it visits every active watch of every
open project. A watch not yet baselined is baselined: every file already there
becomes a silent ``baseline`` row, all at once or not at all. A baselined watch
is scanned: each settled file new to the ledger is parsed, attributed, and
recorded (``review_scan.py``).

It never writes into a watched directory. A directory that cannot be listed is
logged once when it goes bad and once when it recovers, and never stops the
process. A store that cannot record a row does stop it: the error is logged and
re-raised.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Final, Protocol

from amoeba.process.review_scan import content_digest, examine, recording
from amoeba.process.review_sources import (
    DirectoryReviewSource,
    ReviewDirectoryUnavailableError,
    ReviewSource,
    list_review_files,
)
from amoeba.process.settings import ProcessSettings
from amoeba.store import BaselineEntry, ReviewWatch, Store

logger = logging.getLogger(__name__)

#: How this tenant appears in logs, including a grace-expiry ERROR.
REVIEW_DETECTION_TENANT_NAME: Final = "review-detection"

type WatchKey = tuple[str, str]


class DetectionHost(Protocol):
    """What the tenant needs from its host — ``ResidentProcess`` provides it."""

    @property
    def settings(self) -> ProcessSettings: ...

    @property
    def stop_requested(self) -> bool: ...

    @property
    def project_ids(self) -> tuple[str, ...]: ...

    def store_for(self, project_id: str) -> Store: ...


class ReviewDetectionTenant:
    """Baselines and scans registered review directories."""

    def __init__(
        self,
        *,
        version_label: str,
        source_factory: Callable[[Path], ReviewSource] = DirectoryReviewSource,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Build the tenant.

        Args:
            version_label: The ``sq --version`` label captured once at start-up,
                used for files that carry no Squadron stamp.
            source_factory: Builds the source for one watched directory.
            clock: Monotonic seconds, for the scan cadence.
        """
        self._version_label = version_label
        self._source_factory = source_factory
        self._clock = clock
        self._last_scan: float | None = None
        # Kept per watch, so settle signatures persist across ticks.
        self._sources: dict[WatchKey, ReviewSource] = {}
        # The last reason a watch was unreachable; absent means reachable.
        self._unreachable: dict[WatchKey, str] = {}
        # The last reason a baseline could not be taken, per watch.
        self._baseline_blocked: dict[WatchKey, str] = {}

    @property
    def name(self) -> str:
        return REVIEW_DETECTION_TENANT_NAME

    @property
    def version_label(self) -> str:
        return self._version_label

    def tick(self, host: DetectionHost) -> bool:
        """Visit every active watch, at most once per scan interval.

        Returns:
            Whether anything was written.

        Raises:
            Exception: Whatever the store raised while recording; logged first.
        """
        now = self._clock()
        interval = host.settings.review_scan_interval_seconds
        if self._last_scan is not None and now - self._last_scan < interval:
            return False
        self._last_scan = now

        worked = False
        for project_id in host.project_ids:
            if host.stop_requested:
                break
            worked = (
                self._visit_project(host.store_for(project_id), project_id) or worked
            )
        return worked

    def _visit_project(self, store: Store, project_id: str) -> bool:
        worked = False
        for watch in store.watches(project_id):
            if not watch.active:
                continue
            if watch.baselined_at is None:
                worked = self._baseline(store, watch) or worked
            else:
                worked = self._scan(store, watch) or worked
        return worked

    # ----------------------------------------------------------------------
    # Baseline
    # ----------------------------------------------------------------------

    def _baseline(self, store: Store, watch: ReviewWatch) -> bool:
        """Take the all-or-nothing baseline; ``False`` when it must wait."""
        key = (watch.project_id, watch.reviews_dir)
        try:
            paths = list_review_files(Path(watch.reviews_dir))
        except ReviewDirectoryUnavailableError as error:
            self._mark_unreachable(key, str(error))
            return False
        self._mark_reachable(key)

        entries: list[BaselineEntry] = []
        for path in paths:
            try:
                content = path.read_bytes()
            except FileNotFoundError:
                # Specific: deleted between listing and read. A file that is
                # gone is not part of the directory's starting state.
                continue
            except OSError as error:
                # Specific: unreadable. A partial baseline would let this file
                # be ingested later as new, so nothing is written this scan.
                self._block_baseline(key, f"{path} is unreadable: {error}")
                return False
            entries.append(BaselineEntry(str(path), content_digest(content)))

        self._baseline_blocked.pop(key, None)
        recording(
            watch.project_id,
            watch.reviews_dir,
            lambda: store.baseline_watch(watch.project_id, watch.reviews_dir, entries),
        )
        logger.info(
            "baselined %s for %s: %d existing file(s)",
            watch.reviews_dir,
            watch.project_id,
            len(entries),
        )
        return True

    def _block_baseline(self, key: WatchKey, reason: str) -> None:
        if self._baseline_blocked.get(key) != reason:
            logger.warning("cannot baseline %s yet: %s", key[1], reason)
        self._baseline_blocked[key] = reason

    # ----------------------------------------------------------------------
    # Scan
    # ----------------------------------------------------------------------

    def _scan(self, store: Store, watch: ReviewWatch) -> bool:
        """Examine the watch's settled files; ``False`` when it is unreachable."""
        key = (watch.project_id, watch.reviews_dir)
        source = self._sources.get(key)
        if source is None:
            source = self._source_factory(Path(watch.reviews_dir))
            self._sources[key] = source
        try:
            settled = source.poll()
        except ReviewDirectoryUnavailableError as error:
            self._mark_unreachable(key, str(error))
            return False
        self._mark_reachable(key)

        worked = False
        for detected in settled:
            worked = (
                examine(store, watch.project_id, detected, self._version_label)
                or worked
            )
        return worked

    # ----------------------------------------------------------------------
    # Reachability: one ERROR going bad, one INFO recovering, nothing between
    # ----------------------------------------------------------------------

    def _mark_unreachable(self, key: WatchKey, reason: str) -> None:
        if key not in self._unreachable:
            logger.error(
                "watched review directory %s is unreachable: %s", key[1], reason
            )
        self._unreachable[key] = reason

    def _mark_reachable(self, key: WatchKey) -> None:
        if self._unreachable.pop(key, None) is not None:
            logger.info("watched review directory %s is reachable again", key[1])
