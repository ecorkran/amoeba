"""Helpers for the session step tests (slice 263)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from store.message_support import NOW, TTL
from user_configs import user_config

from amoeba.operations.steps.dispatch import StepEdges, run_step
from amoeba.operations.steps.models_session import SessionTickReply
from amoeba.store.deliveries import write_delivery
from amoeba.store.messages import insert_request
from amoeba.store.models import Session
from amoeba.store.sessions import get_session, upsert_session
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent
from amoeba.wire.times import DOOR_VERSION
from operations.message_support import (
    RECIPIENT,
    SENDER,
)

SESSION_ID = "a" * 32
CLIENT_VERSION = "9.8.7"
CONFIG = user_config()
HEARTBEAT = timedelta(seconds=CONFIG.session_heartbeat_seconds)
STALE = timedelta(seconds=CONFIG.session_stale_seconds)
MARKERS = ("MARKER-SUBJECT", "MARKER-BODY", "MARKER-RESULT", "MARKER-REASON")


def run_tick(
    store: Store,
    now: datetime = NOW,
    *,
    session_id: str = SESSION_ID,
    project_id: str = RECIPIENT,
    last_seen: int | None = None,
    push_confirmed: bool = False,
    here: dict[str, str] | None = None,
) -> SessionTickReply:
    document = {
        "here": here if here is not None else {"project_id": project_id},
        "session_id": session_id,
        "client": "claude-code",
        "directory": "/work",
        "client_version": CLIENT_VERSION,
        "last_seen": last_seen,
        "push_confirmed": push_confirmed,
    }
    reply = run_step(
        "session_tick", store, document, StepEdges(lambda: now, lambda: CONFIG)
    )
    assert isinstance(reply, SessionTickReply)
    return reply


def end_session(store: Store, session_id: str = SESSION_ID) -> None:
    run_step(
        "session_end",
        store,
        {"session_id": session_id},
        StepEdges(lambda: NOW, no_config),
    )


def no_config() -> Any:
    raise AssertionError("session_end loads no config")


def row_of(store: Store, session_id: str = SESSION_ID) -> Session | None:
    with store.read() as transaction:
        return get_session(transaction, session_id)


def request_to(
    store: Store, number: int, *, to: str = RECIPIENT, text: str = ""
) -> None:
    with store.write() as transaction:
        insert_request(
            transaction,
            message_id=f"m{number}",
            from_member=SENDER,
            to_member=to,
            parent_id=None,
            parent_depth=None,
            subject=f"subject {text}",
            body=f"body {text}",
            ttl=TTL,
            now=NOW,
        )
        write_delivery(transaction, to, f"m{number}", DeliveryEvent.SENT, NOW)


def seed_row(
    store: Store,
    heartbeat_at: datetime,
    *,
    session_id: str = SESSION_ID,
    member_id: str = RECIPIENT,
) -> None:
    with store.write() as transaction:
        upsert_session(
            transaction,
            Session(
                session_id=session_id,
                member_id=member_id,
                client="claude-code",
                directory="/work",
                started_at=heartbeat_at,
                heartbeat_at=heartbeat_at,
                push_confirmed_at=None,
                client_version="1.0.0",
                door_version=DOOR_VERSION,
            ),
        )
