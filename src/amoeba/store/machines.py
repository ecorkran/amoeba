"""Machines, the owner and the acting machine (slice 260, D12).

The acting machine is whose call is writing: the store stamps its owner, and for a
session its machine, on every record it inserts. A laptop's store acts as the
machine named ``local``; a hub call acts as the machine its token names.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from amoeba.store import sql_machines
from amoeba.store.checkouts import delete_checkouts_on_machine
from amoeba.store.errors import StoreError
from amoeba.store.row_values import (
    encode_timestamp,
    optional_text,
    optional_timestamp,
    text,
)

if TYPE_CHECKING:
    from amoeba.store.store import Store, Transaction

#: The one machine standing for a local install (D12).
LOCAL_MACHINE_NAME: Final = "local"


@dataclass(frozen=True)
class ActingMachine:
    """The machine a store call acts as, with its owner."""

    machine_id: int
    owner_id: int


def the_owner(transaction: Transaction) -> int:
    """The store's one owner id.

    Raises:
        StoreError: ``owners`` does not hold exactly one row.
    """
    rows = transaction.execute(sql_machines.SELECT_OWNER_IDS).fetchall()
    if len(rows) != 1:
        raise StoreError(f"the store must hold exactly one owner, it holds {len(rows)}")
    return int(rows[0][0])


def _find_local(transaction: Transaction) -> tuple[int, int] | None:
    row = transaction.execute(
        sql_machines.SELECT_MACHINE_BY_NAME, (LOCAL_MACHINE_NAME,)
    ).fetchone()
    return None if row is None else (int(row[0]), int(row[1]))


def act_as_local(store: Store) -> ActingMachine:
    """Find or create the machine ``local`` and make it the store's acting machine.

    One read for a store that has ``local`` (D12: it costs one read per open, and
    waits for no write lock); one write the first time. This is what
    ``open_state_store`` and the test fixtures share.
    """
    with store.read() as transaction:
        found = _find_local(transaction)
    if found is None:
        with store.write() as transaction:
            # Re-check under the lock: another process may have made it meanwhile.
            found = _find_local(transaction)
            if found is None:
                owner_id = the_owner(transaction)
                transaction.execute(
                    sql_machines.INSERT_MACHINE_NO_TOKEN,
                    (LOCAL_MACHINE_NAME, owner_id, encode_timestamp(datetime.now(UTC))),
                )
                found = _find_local(transaction)
        if found is None:
            raise StoreError("the machine 'local' is missing after it was inserted")
    machine = ActingMachine(machine_id=found[0], owner_id=found[1])
    store.act_as(machine)
    return machine


def write_closed_mark(
    transaction: Transaction, hub_address: str, now: datetime
) -> None:
    """Set the closed mark, replacing any mark already there (D4).

    From the commit of this transaction no connection can write to the store: every
    write transaction reads the mark first.
    """
    transaction.execute(
        sql_machines.REPLACE_CLOSED_MARK, (hub_address, encode_timestamp(now))
    )


def hash_token(token: str) -> str:
    """SHA-256 of a token, hex. The store keeps only this: a random 256-bit token
    needs no slower hash (D3)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _acting(row: tuple[object, ...] | None) -> ActingMachine | None:
    if row is None:
        return None
    return ActingMachine(machine_id=int(str(row[0])), owner_id=int(str(row[1])))


def invite_machine(
    transaction: Transaction, name: str, token_hash: str, now: datetime
) -> bool:
    """Make the machine with the one owner, or give an existing one a new token.

    Returns whether the machine is new. A re-invite ends the old token at once: the
    hash it matched is gone.
    """
    if transaction.execute(sql_machines.SELECT_MACHINE_BY_NAME, (name,)).fetchone():
        transaction.execute(sql_machines.SET_TOKEN_HASH, (token_hash, name))
        return False
    transaction.execute(
        sql_machines.INSERT_MACHINE,
        (name, the_owner(transaction), token_hash, encode_timestamp(now)),
    )
    return True


def machine_for_token(
    transaction: Transaction, token_hash: str
) -> ActingMachine | None:
    """The machine holding this token hash, by a plain read (D8 step 1)."""
    row = transaction.execute(
        sql_machines.SELECT_MACHINE_BY_TOKEN, (token_hash,)
    ).fetchone()
    return _acting(None if row is None else tuple(row))


def touch_machine(
    transaction: Transaction,
    token_hash: str,
    now: datetime,
    client_version: str | None,
) -> ActingMachine | None:
    """Record a call: sets ``last_called_at`` and ``client_version``.

    A call that sent no client version leaves the stored one as it was. Returns the
    machine, or ``None`` when no row has that hash (the token ended since it was
    read).
    """
    cursor = transaction.execute(
        sql_machines.TOUCH_MACHINE,
        (encode_timestamp(now), client_version, token_hash),
    )
    if cursor.rowcount == 0:
        return None
    return machine_for_token(transaction, token_hash)


def machine_name(transaction: Transaction, machine_id: int) -> str:
    """The machine's name, for the hello reply and the hub log."""
    row = transaction.execute(
        sql_machines.SELECT_MACHINE_NAME, (machine_id,)
    ).fetchone()
    if row is None:
        raise StoreError(f"no machine with id {machine_id}")
    return text(row[0], "machines.name")


@dataclass(frozen=True)
class MachineRow:
    """What `amoeba hub machines` shows of one machine."""

    name: str
    has_token: bool
    last_called_at: datetime | None
    client_version: str | None


def list_machines(transaction: Transaction) -> list[MachineRow]:
    """Every machine, by name."""
    return [
        MachineRow(
            name=text(row[0], "machines.name"),
            has_token=bool(row[1]),
            last_called_at=optional_timestamp(row[2], "machines.last_called_at"),
            client_version=optional_text(row[3], "machines.client_version"),
        )
        for row in transaction.execute(sql_machines.SELECT_MACHINES)
    ]


def remove_machine(transaction: Transaction, name: str) -> bool:
    """Delete the machine, its session rows, its checkouts and its kept results, in the
    caller's one transaction. Returns ``False`` when there is no such machine.

    Members stay; one left with no checkout is shown that way (261 D14). Slice 262 adds
    what else a machine owns (its open questions, waiting answers and wakes) to this
    function (D13).
    """
    found = transaction.execute(sql_machines.SELECT_MACHINE_BY_NAME, (name,)).fetchone()
    if found is None:
        return False
    delete_checkouts_on_machine(transaction, int(found[0]))
    transaction.execute(sql_machines.DELETE_MACHINE_SESSIONS, (name,))
    transaction.execute(sql_machines.DELETE_MACHINE_RESULTS, (name,))
    transaction.execute(sql_machines.DELETE_MACHINE, (name,))
    return True
