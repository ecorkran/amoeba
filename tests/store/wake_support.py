"""Seeding and claiming for the wakes store tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from amoeba.store.models import Session, Wake
from amoeba.store.sessions import upsert_session
from amoeba.store.store import Transaction
from amoeba.store.wakes import WakeLimits, claim_wake
from store.message_support import ADDRESSEE, NOW, PROGRAM
from store.seed import insert_checkout, insert_member

COMMAND = "wake-agent --max-seconds 60"
TIMEOUT_SECONDS = 600
MAX_WAKES = 3
STALE_SECONDS = 90
DIRECTORY = "/work/checkout"
LOG_DIRECTORY = "/state/logs/wake"
HOUR = timedelta(hours=1)
LIMITS = WakeLimits(TIMEOUT_SECONDS, MAX_WAKES, STALE_SECONDS)


def seed_waking_member(
    transaction: Transaction,
    project_id: str = ADDRESSEE,
    command: str | None = COMMAND,
    directory: str | None = DIRECTORY,
) -> None:
    """The member ``project_id`` in the seeded program, with one checkout on the acting
    machine at ``directory`` whose wake command is ``command``; a ``directory`` of
    ``None`` seeds no checkout. The caller seeded the program."""
    insert_member(
        transaction,
        project_id=project_id,
        program_id=PROGRAM,
        rules_paths=(),
        authorize_allow=(),
        authorize_deny=(),
        registered_at=NOW,
        updated_at=NOW,
    )
    if directory is not None:
        insert_checkout(
            transaction,
            member_id=project_id,
            cf_project_id=project_id,
            path=directory,
            wake_command=command,
            now=NOW,
        )


def give_checkout_command(
    transaction: Transaction,
    member_id: str,
    command: str | None,
    directory: str = DIRECTORY,
) -> None:
    """Set ``command`` on the member's first checkout on the acting machine, making
    one at ``directory`` when it has none."""
    if transaction.execute(
        "SELECT 1 FROM checkouts WHERE member_id = ?", (member_id,)
    ).fetchone():
        transaction.execute(
            "UPDATE checkouts SET wake_command = ? WHERE member_id = ?",
            (command, member_id),
        )
        return
    insert_checkout(
        transaction,
        member_id=member_id,
        cf_project_id=member_id,
        path=directory,
        wake_command=command,
        now=NOW,
    )


def claim(
    transaction: Transaction,
    wake_id: str,
    *,
    member_id: str = ADDRESSEE,
    now: datetime = NOW,
    max_wakes: int = MAX_WAKES,
) -> Wake | None:
    return claim_wake(
        transaction,
        member_id,
        now,
        replace(LIMITS, max_per_day=max_wakes),
        wake_id,
        f"{LOG_DIRECTORY}/{wake_id}",
    )


def confirmed_session(
    transaction: Transaction, member_id: str = ADDRESSEE, now: datetime = NOW
) -> None:
    """A fresh session whose agent answered a channel event."""
    upsert_session(
        transaction,
        Session(
            session_id=f"session-{member_id}",
            member_id=member_id,
            client="claude-code",
            directory="/work",
            started_at=now,
            heartbeat_at=now,
            push_confirmed_at=now,
        ),
    )
