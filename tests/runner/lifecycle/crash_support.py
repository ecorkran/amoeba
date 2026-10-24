"""Make a store's k-th node write fail, to simulate a crash mid-reconcile."""

from __future__ import annotations

from typing import Any

from amoeba.store import Store

#: The store methods that write nodes.
NODE_WRITES = (
    "create_node",
    "block",
    "resolve",
    "update_node_status",
    "update_cf_reference",
)


def fail_nth_write(store: Store, n: int, error: Exception) -> None:
    """Raise ``error`` from the ``n``-th node write on ``store`` (counted across
    all of :data:`NODE_WRITES`). Replaces the methods on this instance only."""
    counter = {"writes": 0}

    def wrap(real: Any) -> Any:
        def counted(*args: Any, **kwargs: Any) -> Any:
            counter["writes"] += 1
            if counter["writes"] == n:
                raise error
            return real(*args, **kwargs)

        return counted

    for name in NODE_WRITES:
        setattr(store, name, wrap(getattr(store, name)))


def restore_writes(store: Store) -> None:
    """Remove the instance-level wrappers so the class methods apply again."""
    for name in NODE_WRITES:
        store.__dict__.pop(name, None)
