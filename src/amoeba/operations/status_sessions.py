"""The live sessions ``status`` and ``list`` show under a member (slice 241, D8).

One read of ``live_sessions``, the stale rule's one reader for display, kept to the
members in scope: active members only, so a removed member's session never shows.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from amoeba.operations.status_models import SessionEntry
from amoeba.store.models import Session
from amoeba.store.sessions import live_sessions
from amoeba.store.store import Store


def read_member_sessions(
    store: Store, member_ids: Iterable[str], now: datetime, stale_seconds: float
) -> dict[str, tuple[SessionEntry, ...]]:
    """Each member's fresh sessions, oldest ``started_at`` first."""
    wanted = set(member_ids)
    with store.read() as transaction:
        rows = live_sessions(transaction, now, stale_seconds)
    by_member: dict[str, list[SessionEntry]] = {member: [] for member in wanted}
    for row in rows:
        if row.member_id in wanted:
            by_member[row.member_id].append(_entry(row))
    return {member: tuple(entries) for member, entries in by_member.items()}


def _entry(row: Session) -> SessionEntry:
    return SessionEntry(
        client=row.client,
        directory=row.directory,
        started_at=row.started_at,
        heartbeat_at=row.heartbeat_at,
        push_confirmed_at=row.push_confirmed_at,
    )
