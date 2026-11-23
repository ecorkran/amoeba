"""Checkouts: one copy of a repo on one machine (slice 261, D2, D7, D8).

A checkout holds the Context Forge project id that machine knows the repo by, the
path the repo was registered at, and the wake command to run there. Every function
takes an open transaction. A checkout belongs to the acting machine's call; a wake
command is never set on another machine's checkout (D7).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from amoeba.store import sql_checkouts
from amoeba.store.errors import StoreError
from amoeba.store.row_values import (
    decode_timestamp,
    encode_timestamp,
    integer,
    optional_text,
    text,
)
from amoeba.store.store import Transaction


@dataclass(frozen=True)
class Checkout:
    """One row of ``checkouts``."""

    checkout_id: int
    member_id: str
    machine_id: int
    cf_project_id: str
    path: str
    wake_command: str | None
    added_at: datetime
    updated_at: datetime


def _checkout(row: Sequence[object]) -> Checkout:
    return Checkout(
        checkout_id=integer(row[0], "checkouts.checkout_id"),
        member_id=text(row[1], "checkouts.member_id"),
        machine_id=integer(row[2], "checkouts.machine_id"),
        cf_project_id=text(row[3], "checkouts.cf_project_id"),
        path=text(row[4], "checkouts.path"),
        wake_command=optional_text(row[5], "checkouts.wake_command"),
        added_at=decode_timestamp(row[6], "checkouts.added_at"),
        updated_at=decode_timestamp(row[7], "checkouts.updated_at"),
    )


def insert_checkout(
    transaction: Transaction,
    *,
    member_id: str,
    cf_project_id: str,
    path: str,
    wake_command: str | None,
    now: datetime,
) -> None:
    """Add a checkout on the acting machine, owned by the acting owner."""
    acting = transaction.acting("checkouts")
    stamp = encode_timestamp(now)
    transaction.execute(
        sql_checkouts.INSERT_CHECKOUT,
        (
            member_id,
            acting.machine_id,
            cf_project_id,
            path,
            wake_command,
            acting.owner_id,
            stamp,
            stamp,
        ),
    )


def checkout_at(
    transaction: Transaction, machine_id: int, cf_project_id: str
) -> Checkout | None:
    row = transaction.execute(
        sql_checkouts.SELECT_CHECKOUT_AT, (machine_id, cf_project_id)
    ).fetchone()
    return None if row is None else _checkout(row)


def checkouts_of_member(
    transaction: Transaction, member_id: str
) -> tuple[Checkout, ...]:
    """Every checkout of the member, the one added first first."""
    rows = transaction.execute(
        sql_checkouts.SELECT_CHECKOUTS_OF_MEMBER, (member_id,)
    ).fetchall()
    return tuple(_checkout(row) for row in rows)


def checkout_listing(
    transaction: Transaction, member_id: str
) -> tuple[tuple[Checkout, str], ...]:
    """Each checkout of the member with the name of its machine, the one added first
    first (what ``list members`` shows)."""
    rows = transaction.execute(
        sql_checkouts.SELECT_CHECKOUT_LISTING, (member_id,)
    ).fetchall()
    return tuple((_checkout(row), text(row[8], "machines.name")) for row in rows)


def checkouts_on_machine(
    transaction: Transaction, machine_id: int
) -> tuple[Checkout, ...]:
    rows = transaction.execute(
        sql_checkouts.SELECT_CHECKOUTS_ON_MACHINE, (machine_id,)
    ).fetchall()
    return tuple(_checkout(row) for row in rows)


def first_checkout_on(
    transaction: Transaction, member_id: str, machine_id: int
) -> Checkout | None:
    """The member's checkout on this machine that was added first."""
    row = transaction.execute(
        sql_checkouts.SELECT_FIRST_CHECKOUT_ON, (member_id, machine_id)
    ).fetchone()
    return None if row is None else _checkout(row)


def first_wakeable_checkout(
    transaction: Transaction, member_id: str, machine_id: int | None
) -> Checkout | None:
    """The member's first-added checkout that has a wake command (261 D9).

    On ``machine_id``, or with ``None`` on any machine (what the door's check asks).
    """
    row = (
        transaction.execute(
            sql_checkouts.SELECT_WAKEABLE_CHECKOUT_ANYWHERE, (member_id,)
        ).fetchone()
        if machine_id is None
        else transaction.execute(
            sql_checkouts.SELECT_WAKEABLE_CHECKOUT_ON, (member_id, machine_id)
        ).fetchone()
    )
    return None if row is None else _checkout(row)


def delete_checkout(transaction: Transaction, checkout_id: int) -> None:
    """Delete one checkout by its id."""
    transaction.execute(sql_checkouts.DELETE_CHECKOUT, (checkout_id,))


def delete_checkouts_of_member(transaction: Transaction, member_id: str) -> int:
    return transaction.execute(
        sql_checkouts.DELETE_CHECKOUTS_OF_MEMBER, (member_id,)
    ).rowcount


def delete_checkouts_on_machine(transaction: Transaction, machine_id: int) -> int:
    return transaction.execute(
        sql_checkouts.DELETE_CHECKOUTS_ON_MACHINE, (machine_id,)
    ).rowcount


def delete_checkouts_at_path(
    transaction: Transaction, machine_id: int, path: str
) -> int:
    """Delete this machine's checkouts at ``path``; the number deleted (D8).

    Compared as text with trailing slashes dropped from both sides; the directory
    itself may be gone, so nothing is resolved against the disk.
    """
    return transaction.execute(
        sql_checkouts.DELETE_CHECKOUTS_AT_PATH, (machine_id, path.rstrip("/"))
    ).rowcount


def set_checkout_wake_command(
    transaction: Transaction,
    checkout_id: int,
    command: str | None,
    now: datetime,
) -> None:
    """Set or clear the checkout's wake command.

    Raises:
        StoreError: The checkout is not on the acting machine, or does not exist.
    """
    acting = transaction.acting("checkouts")
    row = transaction.execute(
        sql_checkouts.SELECT_CHECKOUT_MACHINE, (checkout_id,)
    ).fetchone()
    if row is None:
        raise StoreError(f"checkout {checkout_id} does not exist")
    if integer(row[0], "checkouts.machine_id") != acting.machine_id:
        acting_row = transaction.execute(
            sql_checkouts.SELECT_MACHINE_NAME, (acting.machine_id,)
        ).fetchone()
        acting_name = "unknown" if acting_row is None else text(acting_row[0], "name")
        raise StoreError(
            f"checkout {checkout_id} is on machine {text(row[1], 'name')!r}, "
            f"not on the acting machine {acting_name!r}"
        )
    transaction.execute(
        sql_checkouts.SET_CHECKOUT_WAKE_COMMAND,
        (command, encode_timestamp(now), checkout_id),
    )
