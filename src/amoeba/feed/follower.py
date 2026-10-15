"""``follow``: a blocking iterator over a project's change feed (D2).

It reads changes after a cursor in batches. When none are left it waits until
SQLite's ``PRAGMA data_version`` moves, which happens only when another
connection commits, so an idle check costs one pragma read per interval.

Failures (LLD "Follower failures"): a busy read is retried on the next
interval; everything else raises, because later slices build on this
contract. The follower holds no SQL.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from amoeba.store import Change, Store, StoreBusyError, StorePermissionError
from amoeba.store.paths import project_store_path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeedSettings:
    """Follower tuning. Followers run outside the process, so these live here."""

    #: How often an idle follower checks for a commit. The contract's latency
    #: bound: a change reaches a follower within this, plus the read time.
    follow_interval_seconds: float = 0.25
    #: How many changes one read returns at most.
    feed_batch_size: int = 500


def follow(
    store_dir: Path,
    project_id: str,
    *,
    after: int,
    settings: FeedSettings,
    stop: Callable[[], bool] | None = None,
) -> Iterator[Change]:
    """Yield every change after ``after``, then each new one as it commits.

    Args:
        store_dir: The supervisor's store directory.
        project_id: The project whose feed to follow.
        after: The last ``seq`` the caller has seen; 0 for the whole feed.
        settings: Interval and batch size.
        stop: Checked between waits and between yielded changes. Returning
            true ends the iterator cleanly. If it raises, the error propagates.

    Raises:
        StorePermissionError: The store does not exist (unknown project), at
            start or once it disappears mid-follow.
        StoreSchemaError: The store is at another schema version.
    """
    path = project_store_path(store_dir, project_id)
    store = Store.open_read_only(path)
    should_stop = stop if stop is not None else _never
    try:
        cursor = after
        while not should_stop():
            # Captured before the read, so a commit landing between an empty
            # read and the wait still wakes the follower.
            version = store.data_version()
            batch = _read_batch(store, project_id, cursor, settings)
            if batch is None:
                time.sleep(settings.follow_interval_seconds)
                continue
            for change in batch:
                yield change
                cursor = change.seq
                if should_stop():
                    return
            if not batch:
                _wait_for_commit(store, path, version, settings, should_stop)
    finally:
        store.close()


def _never() -> bool:
    return False


def _read_batch(
    store: Store, project_id: str, cursor: int, settings: FeedSettings
) -> list[Change] | None:
    """One read after the cursor; ``None`` when the store was busy this time."""
    try:
        return store.changes(project_id, after=cursor, limit=settings.feed_batch_size)
    except StoreBusyError:
        # Specific: a writer held the lock past the busy timeout. Transient by
        # contract; the caller retries after one interval. The store logged it.
        return None


def _wait_for_commit(
    store: Store,
    path: Path,
    version: int,
    settings: FeedSettings,
    should_stop: Callable[[], bool],
) -> None:
    """Return once ``data_version`` moves past ``version``, or ``stop`` says so."""
    while store.data_version() == version and not should_stop():
        time.sleep(settings.follow_interval_seconds)
        # An open connection keeps reading a deleted file, so absence is
        # checked explicitly rather than waiting forever on a dead store.
        if not path.exists():
            raise StorePermissionError(f"store at {path} no longer exists")
