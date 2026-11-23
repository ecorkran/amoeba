"""The hub's store opener (slice 260, D12, D15).

It lives in ``hub`` and imports nothing from ``client``: the hub must not depend on
the client package, even through ``operations``. The guard therefore names the client
file, not the hub address the client file holds.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing

from amoeba.config.home import StateLayout
from amoeba.operations.name_by_id import name_by_id
from amoeba.store.errors import (
    HubStoreBehindError,
    HubStoreMissingError,
    LocalStoreClosedError,
    NotAHubHomeError,
)
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION, read_schema_version
from amoeba.store.store import Store


def refuse_unless_a_ready_hub(layout: StateLayout) -> None:
    """The guard of every hub admin command, before any store is opened.

    An admin command acts on a hub's store and never migrates one. Without this, a
    command run on an ordinary machine would open and change that machine's own
    store, and one run against an older hub store would migrate it with no backup:
    only ``amoeba hub serve`` migrates, after its pre-migration backup (D15).

    Raises:
        NotAHubHomeError: The config home holds no ``hub.yaml``.
        HubStoreBehindError: The store's schema is older than this code expects.
    """
    if not layout.hub_file.exists():
        raise NotAHubHomeError(
            f"this home is not a hub's: there is no hub config at {layout.hub_file}. "
            "Hub commands run on the machine that serves the hub, and nothing here "
            "was opened"
        )
    if not layout.store_path.exists():
        return  # ``open_hub_store`` reports the missing store
    try:
        with closing(
            sqlite3.connect(
                f"{layout.store_path.absolute().as_uri()}?mode=ro", uri=True
            )
        ) as store:
            version = read_schema_version(store)
    except sqlite3.Error:
        # Not readable as a database: ``Store.open`` reports that with its own
        # error, and it cannot migrate a file it cannot read.
        return
    if version < EXPECTED_SCHEMA_VERSION:
        raise HubStoreBehindError(
            f"the hub's store at {layout.store_path} is at schema {version} and this "
            f"code expects {EXPECTED_SCHEMA_VERSION}. Start it once with "
            "`amoeba hub serve`, which backs it up and then migrates it"
        )


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
    store = Store.open(layout.store_path)
    named = False
    try:
        # A hub has no `cf`: a member left unnamed by schema 11 is named by its id.
        name_by_id(store)
        named = True
    finally:
        if not named:
            store.close()
    return store
