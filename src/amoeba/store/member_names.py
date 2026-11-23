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
from amoeba.store.vocabulary import is_member_name

logger = logging.getLogger(__name__)

#: The highest ``-N`` suffix tried when an id's own name clashes in another case.
NAME_SUFFIX_LIMIT = 99


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


def _name_held_by_another(transaction: Transaction, name: str, member_id: str) -> bool:
    """Whether an active member other than ``member_id`` has ``name``, in any case."""
    holder = active_member_by_name(transaction, name)
    return holder is not None and holder.project_id != member_id


def name_by_own_id(transaction: Transaction, member: UnnamedMember) -> str:
    """The name for a member with nothing better: its own id, or, when the name index
    would refuse that, the id with the first free ``-N`` suffix.

    The index compares without case, so an id can clash with an active member's name
    that differs only in case. Refusing would fail every command that opens the store,
    and the rename command is one of them, so the member is named apart and the log
    says so; ``amoeba add --project ID --name NAME`` renames it.

    Raises:
        StoreRowError: No suffix up to ``NAME_SUFFIX_LIMIT`` is free and valid.
    """
    own = member.project_id
    if member.removed or not _name_held_by_another(transaction, own, own):
        return own  # a removed member's name is not in the index
    for number in range(2, NAME_SUFFIX_LIMIT + 1):
        candidate = f"{own}-{number}"
        if (
            is_member_name(candidate)
            and not _name_held_by_another(transaction, candidate, own)
            and not name_is_other_members_id(transaction, candidate, own)
        ):
            logger.warning(
                "naming: member %s cannot be named by its id (another member has it "
                "in another case), so it is named %s",
                own,
                candidate,
            )
            return candidate
    raise StoreRowError(
        f"member {own!r} cannot be named: its id clashes in another case and no name "
        f"{own}-2 to {own}-{NAME_SUFFIX_LIMIT} is free"
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
