"""Name every unnamed member by its own id (slice 261, D4, "On a hub store").

The hub has no ``cf``, so it cannot give a member its Context Forge name. A hub store
holds an unnamed member only when it was migrated from schema 11: a 260 fixture, or a
backup of one started with ``serve --from-backup``. This still answers it, so such a
member is not a failed read with no way out: each is named by its id, the architecture's
rule for a member ``cf`` does not know.

This module imports only the store and the standard library, because the hub calls it
and ``operations.naming`` imports the client part. It inserts nothing and needs no
acting machine. When nothing is unnamed it is one read and takes no lock.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from amoeba.store.errors import StoreRowError
from amoeba.store.member_names import (
    UnnamedMember,
    active_member_by_name,
    clear_member_wake_command,
    set_member_name,
    unnamed_members,
)
from amoeba.store.store import Store, Transaction

logger = logging.getLogger(__name__)


def _refuse_a_clash(transaction: Transaction, member: UnnamedMember) -> None:
    if member.removed:
        return  # a removed member's name is not in the index
    holder = active_member_by_name(transaction, member.project_id)
    if holder is not None and holder.project_id != member.project_id:
        raise StoreRowError(
            f"member {member.project_id!r} cannot be named by its id: member "
            f"{holder.project_id!r} already has that name in another case"
        )


def name_by_id(store: Store, *, now: datetime | None = None) -> None:
    """Give each unnamed member its id as its name, in one write.

    Ids are unique, but the name index compares without case, so an id can still clash
    with another active member's name or id that differs only in case. That is refused
    loudly, naming both members, rather than left to the index's raw error.

    Raises:
        StoreRowError: An active member's id equals, in another case, a name an active
            member already has.
    """
    with store.read() as transaction:
        if not unnamed_members(transaction):
            return
    stamp = datetime.now(UTC) if now is None else now
    with store.write() as transaction:
        # Re-read under the lock: another call may have named them meanwhile.
        for member in unnamed_members(transaction):
            _refuse_a_clash(transaction, member)
            set_member_name(transaction, member.project_id, member.project_id, stamp)
            logger.info("named member %s by its id", member.project_id)
            if member.wake_command is not None:
                # No checkout exists on a hub store, so no checkout takes the command:
                # it is dropped, and the log keeps it (D4).
                clear_member_wake_command(transaction, member.project_id)
                logger.warning(
                    "naming: member %s has no checkout, so its wake command was "
                    "dropped: %r",
                    member.project_id,
                    member.wake_command,
                )
