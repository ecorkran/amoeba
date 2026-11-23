"""Interim naming and checkout for ``set_up`` (slice 261, 1.1 and 2.3).

Until ``add`` is rewritten around checkouts (task 9.9, which deletes this module),
a member ``set_up`` writes is named by naming's rule (D4): the Context Forge name
when it is a valid member name and nobody has it, else the member's id. A checkout
is written for the directory the member was resolved from, with the Context Forge
id as the member id.
"""

from __future__ import annotations

from datetime import datetime

from amoeba.store.checkouts import checkout_at, insert_checkout
from amoeba.store.member_names import (
    active_member_by_name,
    name_is_other_members_id,
    set_member_name,
)
from amoeba.store.programs import get_member_any
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import is_member_name


def _is_free(transaction: Transaction, name: str, project_id: str) -> bool:
    """Whether ``project_id`` may hold ``name``: valid, and nobody else has it."""
    if not is_member_name(name):
        return False
    holder = active_member_by_name(transaction, name)
    if holder is not None and holder.project_id != project_id:
        return False
    return not name_is_other_members_id(transaction, name, project_id)


def member_name_for_write(
    transaction: Transaction,
    project_id: str,
    context_forge_name: str,
    now: datetime,
) -> str:
    """The name ``upsert_member`` binds for this member.

    A stored name stays. A removed member comes back under its stored name when that
    is still free, else it is renamed to its id first, so the unique index on active
    names is never hit when it is registered again.
    """
    stored = get_member_any(transaction, project_id)
    if stored is None:
        free = _is_free(transaction, context_forge_name, project_id)
        return context_forge_name if free else project_id
    if stored.removed_at is not None and not _is_free(
        transaction, stored.name, project_id
    ):
        set_member_name(transaction, project_id, project_id, now)
    return stored.name


def ensure_checkout(
    transaction: Transaction, project_id: str, path: str, now: datetime
) -> None:
    """A checkout on the acting machine for this Context Forge project, if none."""
    machine_id = transaction.acting("checkouts").machine_id
    if checkout_at(transaction, machine_id, project_id) is None:
        insert_checkout(
            transaction,
            member_id=project_id,
            cf_project_id=project_id,
            path=path,
            wake_command=None,
            now=now,
        )
