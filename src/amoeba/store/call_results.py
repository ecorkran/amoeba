"""Kept results of writing calls, so a repeated call applies once (slice 260, D9)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from amoeba.store import sql_call_results
from amoeba.store.row_values import encode_timestamp, text
from amoeba.store.store import Transaction


@dataclass(frozen=True)
class KeptResult:
    """A kept call: its operation, the SHA-256 of its request body, its reply body."""

    operation: str
    request_hash: str
    reply: str


def find_kept(
    transaction: Transaction, machine_id: int, call_id: str
) -> KeptResult | None:
    """The result kept for this machine's call id, if any."""
    row = transaction.execute(
        sql_call_results.SELECT_KEPT, (machine_id, call_id)
    ).fetchone()
    if row is None:
        return None
    return KeptResult(
        operation=text(row[0], "call_results.operation"),
        request_hash=text(row[1], "call_results.request_hash"),
        reply=text(row[2], "call_results.reply"),
    )


def keep(
    transaction: Transaction,
    machine_id: int,
    call_id: str,
    operation: str,
    request_hash: str,
    reply: str,
    now: datetime,
) -> None:
    """Keep a writing call's reply, in the same transaction as the operation."""
    transaction.execute(
        sql_call_results.INSERT_KEPT,
        (machine_id, call_id, operation, request_hash, reply, encode_timestamp(now)),
    )


def delete_expired(
    transaction: Transaction, now: datetime, lifetime_seconds: float
) -> None:
    """Delete every result kept longer than ``lifetime_seconds`` ago: one statement
    over the ``recorded_at`` index."""
    oldest = now - timedelta(seconds=lifetime_seconds)
    transaction.execute(sql_call_results.DELETE_EXPIRED, (encode_timestamp(oldest),))
