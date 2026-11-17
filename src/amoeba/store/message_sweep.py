"""The sweep: record expiry, then prune what is old (240 D6).

Open requests past ``expires_at`` become ``expired``, with a delivery to each party.
Terminal requests (with their deliveries) and rejection rows older than the retention
are deleted, and so are notes (with their deliveries) older than the retention, read or
not (243 D6), and so are ``wakes`` rows started before it, ended or not (244 D10). Open
and accepted requests are never pruned: each leaves through expiry,
``done``, ``decline`` or ``cancel``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from amoeba.store import sql_messages
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import message_from_row
from amoeba.store.notes import prune_notes
from amoeba.store.row_values import encode_timestamp, integer
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import DeliveryEvent, RequestState
from amoeba.store.wakes import prune_wakes, wakes_due


def sweep(transaction: Transaction, now: datetime, prune_after_days: int) -> None:
    """Expire what is due, then prune what is old. Tests read the rows."""
    due = transaction.execute(
        sql_messages.SELECT_DUE_REQUESTS, (encode_timestamp(now),)
    ).fetchall()
    for row in due:
        change_state(
            transaction,
            message_from_row(row),
            RequestState.EXPIRED,
            DeliveryEvent.EXPIRED,
            None,
            now,
            StateFields(),
        )
    cutoff = _cutoff(now, prune_after_days)
    transaction.execute(sql_messages.DELETE_PRUNABLE_DELIVERIES, (cutoff,))
    transaction.execute(sql_messages.DELETE_PRUNABLE_REQUESTS, (cutoff,))
    transaction.execute(sql_messages.DELETE_OLD_REJECTIONS, (cutoff,))
    prune_notes(transaction, cutoff)
    prune_wakes(transaction, cutoff)


def sweep_due(transaction: Transaction, now: datetime, prune_after_days: int) -> bool:
    """Whether ``sweep`` has anything to do; reads only."""
    cutoff = _cutoff(now, prune_after_days)
    row = transaction.execute(
        sql_messages.SELECT_SWEEP_DUE, (encode_timestamp(now), cutoff, cutoff, cutoff)
    ).fetchone()
    if row is None:
        raise AssertionError("the sweep due check returned no row")
    return integer(row[0], "sweep due") == 1 or wakes_due(transaction, cutoff)


def _cutoff(now: datetime, prune_after_days: int) -> str:
    return encode_timestamp(now - timedelta(days=prune_after_days))
