"""A feed subscriber on a thread, recording every change it sees."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Protocol

from host_harness import EXIT_TIMEOUT_SECONDS

from amoeba.feed import FeedSettings, follow
from amoeba.store import Change

logger = logging.getLogger(__name__)

FOLLOW_INTERVAL_SECONDS = 0.05


class BackgroundReader(Protocol):
    """A thread reading in the background, whose failure must reach the test."""

    @property
    def name(self) -> str: ...

    @property
    def error(self) -> BaseException | None: ...

    def close(self) -> None: ...


class Subscriber:
    """``follow()`` from ``seq`` 0, on a thread.

    A failure inside the thread is stored in ``error`` and re-raised on the main
    thread at the harness's next wait.
    """

    def __init__(self, supervisor_dir: Path, project_id: str) -> None:
        self.project_id = project_id
        self.changes: list[Change] = []
        self.error: BaseException | None = None
        self._supervisor_dir = supervisor_dir
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @property
    def name(self) -> str:
        return f"{self.project_id} feed subscriber"

    def _run(self) -> None:
        settings = FeedSettings(follow_interval_seconds=FOLLOW_INTERVAL_SECONDS)
        try:
            for change in follow(
                self._supervisor_dir,
                self.project_id,
                after=0,
                settings=settings,
                stop=self._stop.is_set,
            ):
                self.changes.append(change)
        except Exception as error:  # noqa: BLE001 - thread boundary: stored, re-raised
            logger.exception("feed subscriber for %s failed", self.project_id)
            self.error = error

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=EXIT_TIMEOUT_SECONDS)
