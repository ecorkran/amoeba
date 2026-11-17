"""Seeding and claiming for the wakes store tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from amoeba.store.models import Session, Wake
from amoeba.store.sessions import upsert_session
from amoeba.store.store import Transaction
from amoeba.store.wakes import WakeLimits, claim_wake
from store.message_support import ADDRESSEE, NOW, PROGRAM
from store.seed import insert_member

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
) -> None:
    """The member ``project_id`` in the seeded program, with ``command`` as its wake
    command. The caller seeded the program."""
    insert_member(
        transaction,
        project_id=project_id,
        program_id=PROGRAM,
        rules_paths=(),
        authorize_allow=(),
        authorize_deny=(),
        registered_at=NOW,
        updated_at=NOW,
        wake_command=command,
    )


def claim(
    transaction: Transaction,
    wake_id: str,
    *,
    member_id: str = ADDRESSEE,
    now: datetime = NOW,
    directory: str | None = DIRECTORY,
    max_wakes: int = MAX_WAKES,
) -> Wake | None:
    return claim_wake(
        transaction,
        member_id,
        now,
        replace(LIMITS, max_per_day=max_wakes),
        wake_id,
        directory,
        None if directory is None else f"{LOG_DIRECTORY}/{wake_id}",
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
