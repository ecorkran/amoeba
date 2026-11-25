"""Serving sessions: register, beat, prune, exit, and who is live (slice 241, D6).

Each serving ``amoeba-mcp`` keeps one row. ``heartbeat`` prunes every member's stale
rows and upserts its own in one write transaction, so the table holds the live rows
plus the rows of servers killed since the last beat of any server.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from amoeba.store import sql_sessions
from amoeba.store.errors import StoreError
from amoeba.store.models import Session
from amoeba.store.programs import get_member
from amoeba.store.row_values import (
    decode_timestamp,
    encode_timestamp,
    integer,
    optional_timestamp,
    text,
)
from amoeba.store.store import Transaction


def _oldest_live_heartbeat(now: datetime, stale_seconds: float) -> str:
    """The ``LIVE_SESSION`` parameter: a heartbeat must be newer than this."""
    return encode_timestamp(now - timedelta(seconds=stale_seconds))


def upsert_session(transaction: Transaction, session: Session) -> None:
    """Insert ``session``, or set its ``heartbeat_at``, ``push_confirmed_at`` and
    versions.

    A row re-created after a prune carries ``session.started_at``, the caller's
    original start time.

    Raises:
        StoreError: The id belongs to another machine; no column was changed.
    """
    confirmed = session.push_confirmed_at
    acting = transaction.acting("sessions")
    cursor = transaction.execute(
        sql_sessions.UPSERT_SESSION,
        (
            session.session_id,
            session.member_id,
            session.client,
            session.directory,
            encode_timestamp(session.started_at),
            encode_timestamp(session.heartbeat_at),
            None if confirmed is None else encode_timestamp(confirmed),
            session.client_version,
            session.door_version,
            acting.owner_id,
            acting.machine_id,
        ),
    )
    if cursor.rowcount != 1:
        raise StoreError(
            f"session {session.session_id} belongs to another machine; "
            "its row was not changed"
        )


def delete_session(transaction: Transaction, session_id: str) -> None:
    """Remove the calling machine's row; an unknown id, or one that belongs to
    another machine, is a no-op."""
    transaction.execute(
        sql_sessions.DELETE_SESSION,
        (session_id, transaction.acting("sessions").machine_id),
    )


def get_session(transaction: Transaction, session_id: str) -> Session | None:
    """The row with this id, of any machine, or ``None``."""
    row = transaction.execute(sql_sessions.SELECT_SESSION, (session_id,)).fetchone()
    return None if row is None else _session(row)


def prune_stale_sessions(
    transaction: Transaction, now: datetime, stale_seconds: float
) -> None:
    """Delete every row, of any member, that is not ``LIVE_SESSION``."""
    transaction.execute(
        sql_sessions.PRUNE_STALE_SESSIONS,
        (_oldest_live_heartbeat(now, stale_seconds),),
    )


def heartbeat(transaction: Transaction, session: Session, stale_seconds: float) -> None:
    """One beat: prune stale rows at ``session.heartbeat_at``, then upsert ``session``.

    The caller runs it inside one write transaction.
    """
    prune_stale_sessions(transaction, session.heartbeat_at, stale_seconds)
    upsert_session(transaction, session)


def live_sessions(
    transaction: Transaction, now: datetime, stale_seconds: float
) -> tuple[Session, ...]:
    """Every fresh row, oldest ``started_at`` first, then by ``session_id``."""
    rows = transaction.execute(
        sql_sessions.SELECT_LIVE_SESSIONS,
        (_oldest_live_heartbeat(now, stale_seconds),),
    ).fetchall()
    return tuple(_session(row) for row in rows)


def live_member_ids(
    transaction: Transaction, now: datetime, stale_seconds: float, door_version: int
) -> frozenset[str]:
    """Active members with a fresh, push-confirmed session on ``door_version``, the
    version the hub serves: the liveness rule 244 wakes by (a session on another
    version cannot take a wake, 263 D6).

    A removed member's server keeps beating (D3); ``get_member`` skips it, so "a
    removed member is not a member" stays written once (``sql.ACTIVE_MEMBER``).
    """
    rows = transaction.execute(
        sql_sessions.SELECT_LIVE_MEMBER_IDS,
        (_oldest_live_heartbeat(now, stale_seconds), door_version),
    ).fetchall()
    member_ids = (text(row[0], "sessions.member_id") for row in rows)
    return frozenset(
        member_id
        for member_id in member_ids
        if get_member(transaction, member_id) is not None
    )


def _session(row: tuple[object, ...]) -> Session:
    return Session(
        session_id=text(row[0], "sessions.session_id"),
        member_id=text(row[1], "sessions.member_id"),
        client=text(row[2], "sessions.client"),
        directory=text(row[3], "sessions.directory"),
        started_at=decode_timestamp(row[4], "sessions.started_at"),
        heartbeat_at=decode_timestamp(row[5], "sessions.heartbeat_at"),
        push_confirmed_at=optional_timestamp(row[6], "sessions.push_confirmed_at"),
        client_version=text(row[7], "sessions.client_version"),
        door_version=integer(row[8], "sessions.door_version"),
    )
