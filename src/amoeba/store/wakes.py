"""Wakes: claim, finish, read and prune (slice 244, D2, D3, D7, D9, D10).

A wake is one ``wakes`` row. ``claim_wake`` is the only writer of a new row and
checks, in one transaction, everything that decides whether a wake may start;
``can_wake`` is the same checks as a read, so the two never differ. Every function
takes the caller's transaction and a ``now`` or a cutoff; nothing here reads the
clock, the config or any layout.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

from amoeba.store import sql_wakes
from amoeba.store.checkouts import Checkout, first_wakeable_checkout
from amoeba.store.machines import acting_machine_id
from amoeba.store.models import Wake
from amoeba.store.programs import get_member
from amoeba.store.row_values import (
    decode_timestamp,
    encode_timestamp,
    integer,
    optional_integer,
    optional_text,
    optional_timestamp,
    text,
    vocabulary,
)
from amoeba.store.sessions import live_member_ids
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import WakeOutcome

#: The rolling window the daily limit counts in (D7).
WAKE_WINDOW: Final = timedelta(hours=24)


@dataclass(frozen=True)
class WakeLimits:
    """What bounds a wake, read from the config by the caller: the store reads none."""

    #: How long a claimed wake may run; fixed into its row as ``deadline_at``.
    timeout_seconds: float
    #: Most wakes started for a member in ``WAKE_WINDOW``, failed starts included.
    max_per_day: int
    #: Age of a heartbeat past which a session counts as gone (241's rule).
    session_stale_seconds: float


@dataclass(frozen=True)
class WakeSummary:
    """What ``list`` shows of a member's wakes (D9)."""

    #: The member's unended row, live or past its deadline; ``None`` when none.
    unended: Wake | None
    #: True when ``unended`` is not live (the negation of ``LIVE_WAKE``).
    overdue: bool
    #: Rows with ``started_at`` in ``WAKE_WINDOW``, whatever their outcome.
    used_in_window: int
    #: The newest row that has ended; ``None`` when none has.
    newest_ended: Wake | None


def _wake(row: Sequence[object]) -> Wake:
    outcome = row[9]
    return Wake(
        wake_id=text(row[0], "wakes.wake_id"),
        member_id=text(row[1], "wakes.member_id"),
        directory=optional_text(row[2], "wakes.directory"),
        command=text(row[3], "wakes.command"),
        started_at=decode_timestamp(row[4], "wakes.started_at"),
        deadline_at=decode_timestamp(row[5], "wakes.deadline_at"),
        log_stem=optional_text(row[6], "wakes.log_stem"),
        command_pid=optional_integer(row[7], "wakes.command_pid"),
        ended_at=optional_timestamp(row[8], "wakes.ended_at"),
        outcome=None
        if outcome is None
        else vocabulary(outcome, WakeOutcome, "wakes.outcome"),
        exit_code=optional_integer(row[10], "wakes.exit_code"),
        detail=optional_text(row[11], "wakes.detail"),
    )


def _window_start(now: datetime) -> str:
    return encode_timestamp(now - WAKE_WINDOW)


def _has_live_wake(transaction: Transaction, member_id: str, now: datetime) -> bool:
    row = transaction.execute(
        sql_wakes.SELECT_LIVE_WAKE_EXISTS, (member_id, encode_timestamp(now))
    ).fetchone()
    if row is None:
        raise AssertionError("the live wake check returned no row")
    return integer(row[0], "live wake") == 1


def _used_in_window(transaction: Transaction, member_id: str, now: datetime) -> int:
    row = transaction.execute(
        sql_wakes.COUNT_WAKES_SINCE, (member_id, _window_start(now))
    ).fetchone()
    if row is None:
        raise AssertionError("the wake count returned no row")
    return integer(row[0], "wake count")


class WakeScope(StrEnum):
    """Whose checkouts a wake check looks at (261 D9)."""

    #: The acting machine's: what a claim starts here.
    ACTING_MACHINE = "acting_machine"
    #: Every machine's: what the door asks to refuse a send it cannot wake for.
    ALL_MACHINES = "all_machines"


def _wakeable_checkout(
    transaction: Transaction,
    member_id: str,
    now: datetime,
    limits: WakeLimits,
    scope: WakeScope,
) -> Checkout | None:
    """The checkout whose command a wake would run when checks 1 to 4 of D2 pass.

    In order, stopping at the first that fails: an active member with a checkout in
    ``scope`` that has a wake command (the first added); no push-confirmed live
    session; no live wake; fewer than ``limits.max_per_day`` rows in ``WAKE_WINDOW``.
    The three conditions after the first are written once, for both scopes.
    """
    if get_member(transaction, member_id) is None:
        return None
    machine_id = (
        acting_machine_id(transaction) if scope is WakeScope.ACTING_MACHINE else None
    )
    checkout = first_wakeable_checkout(transaction, member_id, machine_id)
    if checkout is None:
        return None
    if member_id in live_member_ids(transaction, now, limits.session_stale_seconds):
        return None
    if _has_live_wake(transaction, member_id, now):
        return None
    if _used_in_window(transaction, member_id, now) >= limits.max_per_day:
        return None
    return checkout


def wake_command_of(transaction: Transaction, member_id: str) -> str | None:
    """The command a wake claimed on the acting machine would run for this member:
    its first-added checkout's here that has one (261 D9, D13), or ``None``. Only the
    command is read; the limits are not applied."""
    checkout = first_wakeable_checkout(
        transaction, member_id, acting_machine_id(transaction)
    )
    return None if checkout is None else checkout.wake_command


def can_wake(
    transaction: Transaction,
    member_id: str,
    now: datetime,
    limits: WakeLimits,
    scope: WakeScope = WakeScope.ACTING_MACHINE,
) -> bool:
    """Whether a claim in ``scope`` would pass its checks now; reads only."""
    return _wakeable_checkout(transaction, member_id, now, limits, scope) is not None


def claim_wake(  # noqa: PLR0913 - the claim's checks and what it writes
    transaction: Transaction,
    member_id: str,
    now: datetime,
    limits: WakeLimits,
    wake_id: str,
    log_stem: str,
) -> Wake | None:
    """Insert the member's wake row and return it, or return ``None``.

    The row's directory and command are copied from the member's first-added checkout
    on the acting machine that has a command (261 D9), so a later edit changes
    nothing running. ``None`` means no wake starts: a check failed, or the member has
    no such checkout here. The caller makes ``wake_id`` and ``log_stem`` so this reads
    no layout.
    """
    owner_id = transaction.acting("wakes").owner_id
    checkout = _wakeable_checkout(
        transaction, member_id, now, limits, WakeScope.ACTING_MACHINE
    )
    if checkout is None or checkout.wake_command is None:
        return None
    stamp = encode_timestamp(now)
    deadline = encode_timestamp(now + timedelta(seconds=limits.timeout_seconds))
    transaction.execute(
        sql_wakes.INSERT_WAKE,
        (
            wake_id,
            member_id,
            checkout.path,
            checkout.wake_command,
            stamp,
            deadline,
            log_stem,
            None,
            None,
            None,
            None,
            None,
            owner_id,
        ),
    )
    wake = get_wake(transaction, wake_id)
    if wake is None:
        raise AssertionError("the wake row just inserted is missing")
    return wake


def get_wake(transaction: Transaction, wake_id: str) -> Wake | None:
    row = transaction.execute(sql_wakes.SELECT_WAKE, (wake_id,)).fetchone()
    return None if row is None else _wake(row)


def set_command_pid(transaction: Transaction, wake_id: str, pid: int) -> bool:
    """Record the command's pid; ``False`` when the row already has one (another run
    of the same wake started a command first), has ended, or does not exist."""
    cursor = transaction.execute(sql_wakes.SET_COMMAND_PID, (pid, wake_id))
    return cursor.rowcount == 1


def finish_wake(
    transaction: Transaction,
    wake_id: str,
    outcome: WakeOutcome,
    exit_code: int | None,
    detail: str | None,
    now: datetime,
) -> bool:
    """End the row; ``False`` when it was already ended or does not exist."""
    cursor = transaction.execute(
        sql_wakes.FINISH_WAKE,
        (encode_timestamp(now), outcome.value, exit_code, detail, wake_id),
    )
    return cursor.rowcount == 1


def wake_summary(
    transaction: Transaction, member_id: str, now: datetime
) -> WakeSummary:
    """The three things ``list`` shows of a member's wakes (D9)."""
    unended = transaction.execute(
        sql_wakes.SELECT_UNENDED_WAKE, (encode_timestamp(now), member_id)
    ).fetchone()
    ended = transaction.execute(
        sql_wakes.SELECT_NEWEST_ENDED_WAKE, (member_id,)
    ).fetchone()
    return WakeSummary(
        unended=None if unended is None else _wake(unended),
        # ``LIVE_WAKE`` negated in SQL, so the predicate is written once.
        overdue=unended is not None and integer(unended[12], "wake overdue") == 1,
        used_in_window=_used_in_window(transaction, member_id, now),
        newest_ended=None if ended is None else _wake(ended),
    )


def prune_wakes(transaction: Transaction, cutoff: str) -> int:
    """Delete rows started before ``cutoff`` whatever their state; the count.

    ``cutoff`` is an encoded timestamp, as the other prunes take.
    """
    return transaction.execute(sql_wakes.DELETE_AGED_WAKES, (cutoff,)).rowcount


def wakes_due(transaction: Transaction, cutoff: str) -> bool:
    """Whether ``prune_wakes`` would delete anything; reads only."""
    row = transaction.execute(sql_wakes.SELECT_AGED_WAKE_EXISTS, (cutoff,)).fetchone()
    if row is None:
        raise AssertionError("the aged wake check returned no row")
    return integer(row[0], "aged wake") == 1
