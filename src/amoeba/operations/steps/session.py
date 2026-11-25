"""``session_tick`` and ``session_end``: the hub side of a serving session (263 D2).

A tick works out the session's member from the caller's project, refreshes the
session's row when a refresh is due, and answers with what is new for the member.
Every time it writes is the clock of whoever runs the step (D5): no time comes from
the session. The tick reads three config keys and nothing else of it.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from amoeba.config.user_config import UserConfig
from amoeba.operations.caller import find_caller
from amoeba.operations.steps.context import StepContext
from amoeba.operations.steps.models_session import (
    SessionEndReply,
    SessionEndRequest,
    SessionTickReply,
    SessionTickRequest,
    TickEntry,
)
from amoeba.program_version import program_version
from amoeba.store.deliveries import highest_assigned_seq
from amoeba.store.machines import acting_machine_id
from amoeba.store.models import Member, Session
from amoeba.store.push_reads import member_high_seq, push_rows_after
from amoeba.store.sessions import (
    delete_session,
    get_session,
    prune_stale_sessions,
    upsert_session,
)
from amoeba.store.store import Transaction
from amoeba.wire.protocol import CHANNEL_EVENT_MAX_ENTRIES


def _due(
    row: Session | None,
    member_id: str,
    push_confirmed: bool,
    now: datetime,
    config: UserConfig,
) -> bool:
    """D2's rule: no row, a heartbeat that old, another member, or a new push
    confirmation."""
    if row is None or row.member_id != member_id:
        return True
    if now - row.heartbeat_at >= timedelta(seconds=config.session_heartbeat_seconds):
        return True
    return push_confirmed and row.push_confirmed_at is None


def _refresh(
    context: StepContext,
    config: UserConfig,
    request: SessionTickRequest,
    member_id: str,
) -> None:
    """One write: stale rows of every member go, and this row is upserted."""
    transaction, now = context.transaction, context.now
    prune_stale_sessions(transaction, now, config.session_stale_seconds)
    kept = get_session(transaction, request.session_id)
    confirmed_at = None if kept is None else kept.push_confirmed_at
    if confirmed_at is None and request.push_confirmed:
        confirmed_at = now
    upsert_session(
        transaction,
        Session(
            session_id=request.session_id,
            member_id=member_id,
            client=request.client,
            directory=request.directory,
            started_at=now if kept is None else kept.started_at,
            heartbeat_at=now,
            push_confirmed_at=confirmed_at,
            client_version=program_version(),
            door_version=context.door_version,
        ),
    )


def session_tick(context: StepContext, request: SessionTickRequest) -> SessionTickReply:
    """The step ``session_tick``.

    Raises:
        StoreError: The session id belongs to another machine.
    """
    config = context.require_config()
    transaction = context.transaction
    found = find_caller(transaction, acting_machine_id(transaction), request.here)
    if not isinstance(found, Member):
        delete_session(transaction, request.session_id)
        return SessionTickReply(
            member_id=None,
            member_name=None,
            reason=str(found),
            high_seq=0,
            first_seq=None,
            count=0,
            entries=(),
            as_of_seq=0,
            notify_poll_seconds=float(config.notify_poll_seconds),
        )
    member_id = found.project_id
    row = get_session(transaction, request.session_id)
    if _due(row, member_id, request.push_confirmed, context.now, config):
        _refresh(context, config, request, member_id)
    return _reply(transaction, config, request, found)


def _reply(
    transaction: Transaction,
    config: UserConfig,
    request: SessionTickRequest,
    member: Member,
) -> SessionTickReply:
    high = member_high_seq(transaction, member.project_id)
    rows = ()
    if request.last_seen is not None and request.last_seen < high:
        rows = push_rows_after(transaction, member.project_id, request.last_seen)
    listed = rows[:CHANNEL_EVENT_MAX_ENTRIES]
    return SessionTickReply(
        member_id=member.project_id,
        member_name=member.name,
        reason=None,
        high_seq=high,
        first_seq=rows[0].seq if rows else None,
        count=len(rows),
        entries=tuple(
            TickEntry(
                seq=row.seq,
                event=row.event,
                kind=row.kind,
                counterparty=row.counterparty,
            )
            for row in listed
        ),
        as_of_seq=highest_assigned_seq(transaction),
        notify_poll_seconds=float(config.notify_poll_seconds),
    )


def session_end(context: StepContext, request: SessionEndRequest) -> SessionEndReply:
    """The step ``session_end``: delete the calling machine's row; no row is done."""
    delete_session(context.transaction, request.session_id)
    return SessionEndReply()


def write_behind_session(
    transaction: Transaction,
    now: datetime,
    member_id: str,
    session_id: str,
    client: str,
    directory: str,
    client_version: str,
    door_version: int,
) -> None:
    """Keep or make the row of a session whose tick was refused for its door version,
    with the versions the caller sent (D6). The row's start and push confirmation stay.

    Raises:
        StoreError: The session id belongs to another machine.
    """
    kept = get_session(transaction, session_id)
    upsert_session(
        transaction,
        Session(
            session_id=session_id,
            member_id=member_id,
            client=client,
            directory=directory,
            started_at=now if kept is None else kept.started_at,
            heartbeat_at=now,
            push_confirmed_at=None if kept is None else kept.push_confirmed_at,
            client_version=client_version,
            door_version=door_version,
        ),
    )
