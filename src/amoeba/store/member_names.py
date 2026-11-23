"""Member names and ``origin`` in the store (slice 261, D1 to D4).

Reads find a member by its name or its ``origin`` and write a new one. Every
function takes an open transaction. A name is compared without regard to case;
``origin`` is the reduced remote that ``operations.origin`` produces.
"""

from __future__ import annotations

from datetime import datetime

from amoeba.store import sql
from amoeba.store.models import Member
from amoeba.store.programs import member_from_row
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Transaction


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
