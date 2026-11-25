"""The store's typed errors, so no caller mistakes a failure for an empty store."""

from __future__ import annotations

import sqlite3
from pathlib import Path

#: SQLite primary result codes. ``sqlite_errorcode`` may carry an extended code in
#: the upper bits; the low byte is the primary code.
PRIMARY_CODE_MASK = 0xFF


class StoreError(Exception):
    """Base of every store failure."""


class StoreBusyError(StoreError):
    """The store stayed locked for the whole busy timeout."""


class StorePermissionError(StoreError):
    """The store or its directory cannot be created, read or written."""


class StoreCorruptError(StoreError):
    """The file is not a readable SQLite database."""


class StoreSchemaError(StoreError):
    """The store is stamped newer than this code, or its migrations are unusable."""


class StoreIntegrityError(StoreError):
    """A schema constraint (foreign key, unique, check) refused a write."""


class StoreRelocateError(StoreError):
    """Moving the legacy store to the state home failed or did not verify.

    The old store is untouched and any partial copy is gone, so the next call
    tries the move again.
    """


class NoActingMachineError(StoreError):
    """A record was inserted into a store that has no acting machine set.

    The owner and the machine of a record come from the acting machine; there is no
    default. A local store sets ``local`` when it is opened (``open_state_store``); a
    hub call sets the calling machine.
    """


class SessionOfAnotherMachineError(StoreError):
    """A session id is already a row of another machine; nothing was changed."""


class LocalStoreClosedError(StoreError):
    """The local store was set aside for a hub, or this machine is joined to one."""


class HubHomeError(StoreError):
    """The home is a hub's (its config directory holds ``hub.yaml``), not a client's."""


class HubStoreMissingError(StoreError):
    """The hub has no store at its store path; only a first start makes one."""


class NotAHubHomeError(StoreError):
    """A hub admin command was run in a home that is not a hub's (no ``hub.yaml``)."""


class HubStoreBehindError(StoreError):
    """The hub's store needs migrating, which only ``amoeba hub serve`` does."""


class StoreRowError(StoreError):
    """A stored value is not what its column promises."""


def store_error_for(
    error: sqlite3.Error, *, path: Path, busy_timeout_seconds: float
) -> StoreError:
    """The typed error for a sqlite3 failure on the store at ``path``."""
    code = (getattr(error, "sqlite_errorcode", None) or 0) & PRIMARY_CODE_MASK
    if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
        return StoreBusyError(
            f"store at {path} stayed locked for {busy_timeout_seconds}s: {error}"
        )
    if code in (sqlite3.SQLITE_NOTADB, sqlite3.SQLITE_CORRUPT):
        return StoreCorruptError(f"cannot read store at {path}: {error}")
    if code in (sqlite3.SQLITE_CANTOPEN, sqlite3.SQLITE_PERM, sqlite3.SQLITE_READONLY):
        return StorePermissionError(f"cannot use store at {path}: {error}")
    if code == sqlite3.SQLITE_CONSTRAINT:
        return StoreIntegrityError(f"store constraint refused a write: {error}")
    return StoreError(f"unexpected sqlite error on store at {path}: {error}")
