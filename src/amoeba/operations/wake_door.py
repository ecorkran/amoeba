"""What ``send`` does when it runs on the hub, which starts no wake (slice 261, D9).

Through the door this slice does not start wakes; slice 262 does. So the hub part of
``send`` checks, before it writes, whether a wake would be due on any machine: the
recipient has a checkout with a command on some machine, and the other conditions of a
claim hold. If so the call is refused as ``not_served``, nothing is written, and the
message names the member and the machines with a command. Writing the request and
skipping the wake would leave it waiting for a wake no code in this slice can start.
"""

from __future__ import annotations

from datetime import datetime

from amoeba.config.user_config import UserConfig
from amoeba.operations.errors import NOT_SERVED, CallRefused
from amoeba.operations.steps.limits import wake_limits
from amoeba.store.checkouts import checkout_listing
from amoeba.store.programs import get_member
from amoeba.store.store import Store
from amoeba.store.wakes import WakeScope, wake_conditions_hold


def refuse_a_wake_the_door_cannot_start(
    store: Store, config: UserConfig, member_id: str, now: datetime
) -> None:
    """Raise ``CallRefused`` (``not_served``) when a wake is due for ``member_id`` on
    any machine; return when none is.

    Raises:
        CallRefused: A wake is due, and the door does not start wakes yet.
    """
    with store.read() as transaction:
        if not wake_conditions_hold(
            transaction, member_id, now, wake_limits(config), WakeScope.ALL_MACHINES
        ):
            return
        member = get_member(transaction, member_id)
        listing = checkout_listing(transaction, member_id)
    name = member_id if member is None else member.name
    machines = [machine for checkout, machine in listing if checkout.wake_command]
    raise CallRefused(
        NOT_SERVED,
        f"{name} has a wake command on {', '.join(machines)}, and the door does not "
        "start wakes yet, so this request was not written; remove that wake command "
        "(`amoeba add --no-wake-command` in the checkout) to send it",
    )
