"""A wake command on the caller's checkout (slice 261, D7).

The command is a checkout's setting, so it is set on the checkout of the working
directory: the one at (the acting machine, the working directory's Context Forge id).
The resolver has already refused a command given for any other entry.
"""

from __future__ import annotations

from datetime import datetime

from amoeba.operations.set_up_models import Change, ChangeSubject, ChangeVerb
from amoeba.operations.set_up_resolve import ResolvedMember
from amoeba.store.checkouts import checkout_at, set_checkout_wake_command
from amoeba.store.machines import acting_machine_id
from amoeba.store.store import Transaction
from amoeba.upstream.context_forge.project_of import CFProject, CFProjectNotFound


def apply_wake_commands(
    transaction: Transaction,
    members: tuple[ResolvedMember, ...],
    working: CFProject | CFProjectNotFound,
    now: datetime,
    already: list[Change],
) -> list[Change]:
    """Set each given command (``None`` clears) on the working directory's checkout.

    A change record says the member was updated, unless this call already added or
    updated it.
    """
    changes: list[Change] = []
    recorded = {
        change.detail for change in already if change.subject is ChangeSubject.MEMBER
    }
    for member in members:
        if not member.wake_command_given:
            continue
        if isinstance(working, CFProjectNotFound):
            raise ValueError("a wake command was accepted with no working project")
        machine_id = acting_machine_id(transaction)
        checkout = checkout_at(transaction, machine_id, working.id)
        if checkout is None:
            raise ValueError(
                f"no checkout at the working directory's project {working.id!r}"
            )
        if checkout.wake_command == member.wake_command:
            continue
        set_checkout_wake_command(
            transaction, checkout.checkout_id, member.wake_command, now
        )
        if member.project_id not in recorded:
            changes.append(
                Change(
                    verb=ChangeVerb.UPDATED,
                    subject=ChangeSubject.MEMBER,
                    detail=member.project_id,
                )
            )
    return changes
