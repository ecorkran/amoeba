"""Seeding and claiming for the wakes store tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from amoeba.store.models import Session, Wake
from amoeba.store.row_values import decode_timestamp
from amoeba.store.sessions import upsert_session
from amoeba.store.store import Transaction
from amoeba.store.wakes import WakeLimits, claim_wake
from store.message_support import ADDRESSEE, NOW, PROGRAM
from store.seed import insert_checkout, insert_member, mark_wake_wanted

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
    """Claim a wake for the member as a ``send`` that wanted one would have: a mark
    is written first, just after the member's newest wake so each claim answers its
    own mark (262 D8)."""
    if transaction.execute(
        "SELECT 1 FROM members WHERE project_id = ?", (member_id,)
    ).fetchone():
        mark_wake_wanted(
            transaction, member_id, _mark_time(transaction, member_id, now)
        )
    claimed = claim_wake(
        transaction,
        member_id,
        now,
        replace(LIMITS, max_per_day=max_wakes),
        wake_id,
        f"{LOG_DIRECTORY}/{wake_id}",
    )
    # The wake answers its mark; the seeded request is ended so it shows in no listing.
    transaction.execute(
        "UPDATE messages SET state = 'cancelled', reason = 'seeded mark' "
        "WHERE message_id LIKE 'wake-mark-%' AND state = 'open'"
    )
    return claimed


def _mark_time(transaction: Transaction, member_id: str, now: datetime) -> datetime:
    """``now``, or just after the member's newest wake when that is later: a wake
    claimed at or after a mark answers it, so a second claim needs a newer mark."""
    row = transaction.execute(
        "SELECT MAX(started_at) FROM wakes WHERE member_id = ?", (member_id,)
    ).fetchone()
    if row is None or row[0] is None:
        return now
    return max(
        now, decode_timestamp(row[0], "wakes.started_at") + timedelta(microseconds=1)
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
