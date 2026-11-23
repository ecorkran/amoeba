"""Open a store for a test the way the local opener does: acting as ``local``."""

from __future__ import annotations

from pathlib import Path

from amoeba.store.machines import act_as_local
from amoeba.store.store import Store


def open_local_store(path: Path, *, busy_timeout_seconds: float | None = None) -> Store:
    """``Store.open`` then ``act_as_local``, so inserts carry an owner and machine."""
    store = (
        Store.open(path)
        if busy_timeout_seconds is None
        else Store.open(path, busy_timeout_seconds=busy_timeout_seconds)
    )
    act_as_local(store)
    return store
