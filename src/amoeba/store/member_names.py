"""Member names and ``origin`` in the store (slice 261, D1 to D4).

Reads find a member by its name or its ``origin`` and write a new one. Every
function takes an open transaction. A name is compared without regard to case;
``origin`` is the reduced remote that ``operations.origin`` produces.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from amoeba.store import sql
from amoeba.store.errors import StoreRowError
from amoeba.store.models import Member
from amoeba.store.programs import member_from_row
from amoeba.store.row_values import encode_timestamp, integer, optional_text, text
from amoeba.store.store import Transaction

logger = logging.getLogger(__name__)


def active_member_by_name(transaction: Transaction, name: str) -> Member | None:
    """The active member with this name, in any case."""
    row = transaction.execute(sql.SELECT_MEMBER_BY_NAME, (name,)).fetchone()
    return None if row is None else member_from_row(row)


def active_member_by_origin(transaction: Transaction, origin: str) -> Member | None:
    row = transaction.execute(sql.SELECT_MEMBER_BY_ORIGIN, (origin,)).fetchone()
    return None if row is None else member_from_row(row)


def removed_member_by_origin(transaction: Transaction, origin: str) -> Member | None:
    """The most recently removed member with this ``origin``."""
    row = transaction.execute(sql.SELECT_REMOVED_MEMBER_BY_ORIGIN, (origin,)).fetchone()
    return None if row is None else member_from_row(row)


def name_is_other_members_id(
    transaction: Transaction, name: str, member_id: str
) -> bool:
    """Whether ``name`` is the id of a member other than ``member_id`` (D1).

    Active or removed, and in any case, because ``find_member`` tries the name first.
    """
    row = transaction.execute(
        sql.SELECT_NAME_IS_OTHER_MEMBERS_ID, (name, member_id)
    ).fetchone()
    return row is not None


def set_member_name(
    transaction: Transaction, member_id: str, name: str, now: datetime
) -> None:
    transaction.execute(sql.SET_MEMBER_NAME, (name, encode_timestamp(now), member_id))


def set_member_origin(
    transaction: Transaction, member_id: str, origin: str | None, now: datetime
) -> None:
    transaction.execute(
        sql.SET_MEMBER_ORIGIN, (origin, encode_timestamp(now), member_id)
    )


@dataclass(frozen=True)
class UnnamedMember:
    """A member row from before migration 012 that naming has not reached (D4)."""

    project_id: str
    removed: bool
    #: The old ``members.wake_command``, which naming moves to the member's checkout.
    wake_command: str | None


def unnamed_members(transaction: Transaction) -> tuple[UnnamedMember, ...]:
    """Every unnamed member, in registration order; empty once naming has run."""
    rows = transaction.execute(sql.SELECT_UNNAMED_MEMBERS).fetchall()
    return tuple(
        UnnamedMember(
            project_id=text(row[0], "members.project_id"),
            removed=bool(integer(row[1], "members.removed_at")),
            wake_command=optional_text(row[2], "members.wake_command"),
        )
        for row in rows
    )


def clear_member_wake_command(transaction: Transaction, member_id: str) -> None:
    """Set the retired ``members.wake_command`` to null (D4)."""
    transaction.execute(sql.CLEAR_MEMBER_WAKE_COMMAND, (member_id,))


def refuse_id_clash(transaction: Transaction, member: UnnamedMember) -> None:
    """Refuse naming ``member`` by its own id when the name index would: an active
    member already has that name in another case. The index compares without case, so
    the write would fail with its raw error and so would every command, until someone
    read it; this says which two members instead.

    Raises:
        StoreRowError: An active member already has the id as its name, in another case.
    """
    if member.removed:
        return  # a removed member's name is not in the index
    holder = active_member_by_name(transaction, member.project_id)
    if holder is not None and holder.project_id != member.project_id:
        raise StoreRowError(
            f"member {member.project_id!r} cannot be named by its id: member "
            f"{holder.project_id!r} already has that name in another case"
        )


def retire_wake_command(
    transaction: Transaction, member: UnnamedMember, took: bool
) -> None:
    """Null the member's old command now that nothing reads it (D2, D4). ``took`` says a
    checkout took it. A command no checkout took is dropped, and the log line keeps it
    so it can be set again with ``amoeba add --wake-command`` once the member has a
    checkout. It is logged whole on purpose (261 D4): the column was its only copy and
    the store holds it in plain text already, so the log is no wider than the store."""
    if member.wake_command is None:
        return
    clear_member_wake_command(transaction, member.project_id)
    if not took:
        logger.warning(
            "naming: member %s has no checkout, so its wake command was dropped: %r",
            member.project_id,
            member.wake_command,
        )
