"""The hub's store opener (slice 260, D12, D15).

It lives in ``hub`` and imports nothing from ``client``: the hub must not depend on
the client package, even through ``operations``. The guard therefore names the client
file, not the hub address the client file holds.
"""

from __future__ import annotations

from amoeba.config.home import StateLayout
from amoeba.store.errors import HubStoreMissingError, LocalStoreClosedError
from amoeba.store.store import Store


def open_hub_store(layout: StateLayout, *, create: bool = False) -> Store:
    """Open the hub's store, with no machine and no acting machine (D12).

    Only step 7 of a first start passes ``create=True``. Everything else (a serving
    hub, every admin command, a backup) opens a store that must already exist, so a
    store file that goes missing is never replaced by an empty one.

    Raises:
        LocalStoreClosedError: The home holds a client file, so it is a client's
            (the guard of D2).
        HubStoreMissingError: There is no store file and ``create`` is false; raised
            before ``Store.open`` and before any directory is made.
    """
    if layout.client_file.exists():
        raise LocalStoreClosedError(
            f"this home holds a client file ({layout.client_file}), so it is a "
            "client's and has no hub store. Run `amoeba leave` to go back to a "
            "local store"
        )
    if not create and not layout.store_path.exists():
        raise HubStoreMissingError(
            f"the hub has no store at {layout.store_path}; `amoeba hub serve` makes "
            "one on a first start"
        )
    return Store.open(layout.store_path)
