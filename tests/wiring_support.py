"""Shared by the wiring and MCP tests: record the stores opened and whether each
was closed, whichever thread closed it."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import pytest

from amoeba import wiring
from amoeba.config.home import StateLayout
from amoeba.store.store import Store


@dataclass
class TrackedStore:
    """A store ``wiring.open_store`` opened, and whether it has been closed.

    Closure is recorded by the store's own ``close``, so it can be asked from a
    thread other than the worker's (SQLite objects cannot be used across threads).
    """

    store: Store
    closed: threading.Event = field(default_factory=threading.Event)


def is_closed(tracked: TrackedStore) -> bool:
    """Whether ``tracked``'s store has been closed."""
    return tracked.closed.is_set()


def record_opened_stores(monkeypatch: pytest.MonkeyPatch) -> list[TrackedStore]:
    """Every store ``wiring.open_store`` opens from now on, in order."""
    tracked_stores: list[TrackedStore] = []
    real_open = wiring.open_store

    def recording_open(layout: StateLayout) -> Store:
        store = real_open(layout)
        tracked = TrackedStore(store)
        real_close = store.close

        def close() -> None:
            real_close()
            tracked.closed.set()

        monkeypatch.setattr(store, "close", close)
        tracked_stores.append(tracked)
        return store

    monkeypatch.setattr(wiring, "open_store", recording_open)
    return tracked_stores
