"""Sessions: register, beat, prune, exit and the live reads (slice 241, D6, 3.4)."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from store_open import open_local_store

from amoeba.store.models import Session
from amoeba.store.programs import remove_member
from amoeba.store.sessions import (
    delete_session,
    heartbeat,
    live_member_ids,
    live_sessions,
    prune_stale_sessions,
    upsert_session,
)
from amoeba.store.store import Store
from amoeba.wire.times import DOOR_VERSION
from store.message_support import ADDRESSEE, NOW, SENDER, THIRD, count, seed_members

STALE_SECONDS = 90
STALE = timedelta(seconds=STALE_SECONDS)
TICK = timedelta(microseconds=1)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_members(transaction, SENDER, ADDRESSEE, THIRD)
        yield opened


def _session(
    session_id: str,
    *,
    member_id: str = ADDRESSEE,
    started_at: datetime = NOW,
    heartbeat_at: datetime = NOW,
    push_confirmed_at: datetime | None = None,
) -> Session:
    return Session(
        session_id=session_id,
        member_id=member_id,
        client="claude-code",
        directory=f"/work/{member_id}",
        started_at=started_at,
        heartbeat_at=heartbeat_at,
        push_confirmed_at=push_confirmed_at,
        client_version="9.9.9",
        door_version=DOOR_VERSION,
    )


def _write(store: Store, *sessions: Session) -> None:
    with store.write() as transaction:
        for session in sessions:
            upsert_session(transaction, session)


def _live(store: Store, now: datetime = NOW) -> tuple[Session, ...]:
    with store.read() as transaction:
        return live_sessions(transaction, now, STALE_SECONDS)


def _live_members(store: Store, now: datetime = NOW) -> frozenset[str]:
    with store.read() as transaction:
        return live_member_ids(transaction, now, STALE_SECONDS, DOOR_VERSION)


def test_upsert_inserts_then_updates_only_the_beat_and_the_confirmation(
    store: Store,
) -> None:
    first = _session("s1")
    _write(store, first)
    later = NOW + timedelta(seconds=30)
    beat = dataclasses.replace(
        first,
        client="other-client",
        directory="/elsewhere",
        started_at=later,
        heartbeat_at=later,
        push_confirmed_at=later,
        client_version="9.9.9",
        door_version=DOOR_VERSION,
    )

    _write(store, beat)

    (stored,) = _live(store, later)
    assert stored == dataclasses.replace(
        first, heartbeat_at=later, push_confirmed_at=later
    )


def test_a_row_recreated_after_a_prune_carries_the_original_start(
    store: Store,
) -> None:
    session = _session("s1")
    _write(store, session)
    woke = NOW + STALE + timedelta(seconds=10)
    with store.write() as transaction:
        prune_stale_sessions(transaction, woke, STALE_SECONDS)
    assert count_sessions(store) == 0

    with store.write() as transaction:
        heartbeat(
            transaction, dataclasses.replace(session, heartbeat_at=woke), STALE_SECONDS
        )

    (stored,) = _live(store, woke)
    assert stored.started_at == NOW
    assert stored.heartbeat_at == woke


def count_sessions(store: Store) -> int:
    with store.read() as transaction:
        return count(transaction, "sessions")


@pytest.mark.parametrize(
    ("age", "shown"),
    [(STALE - TICK, True), (STALE, False), (STALE + TICK, False)],
    ids=["just-inside", "exactly-at", "past"],
)
def test_live_sessions_draws_the_stale_line_at_the_limit(
    store: Store, age: timedelta, shown: bool
) -> None:
    _write(store, _session("s1", heartbeat_at=NOW - age))

    assert bool(_live(store)) is shown


def test_live_sessions_are_oldest_start_first_then_by_session_id(
    store: Store,
) -> None:
    early = NOW - timedelta(minutes=5)
    _write(
        store,
        _session("s-late", started_at=NOW),
        _session("s-b", started_at=early),
        _session("s-a", started_at=early),
    )

    assert [session.session_id for session in _live(store)] == ["s-a", "s-b", "s-late"]


def test_live_member_ids_needs_a_fresh_confirmed_row(store: Store) -> None:
    _write(
        store,
        _session("confirmed", member_id=ADDRESSEE, push_confirmed_at=NOW),
        _session("unconfirmed", member_id=SENDER),
        _session(
            "stale-confirmed",
            member_id=THIRD,
            heartbeat_at=NOW - STALE,
            push_confirmed_at=NOW - STALE,
        ),
    )

    assert _live_members(store) == frozenset({ADDRESSEE})


def test_live_member_ids_leaves_out_a_removed_member(store: Store) -> None:
    _write(store, _session("confirmed", member_id=ADDRESSEE, push_confirmed_at=NOW))
    with store.write() as transaction:
        assert remove_member(transaction, ADDRESSEE, NOW)

    assert _live_members(store) == frozenset()


def test_one_servers_prune_deletes_every_members_stale_rows_and_keeps_live_ones(
    store: Store,
) -> None:
    _write(
        store,
        _session("dead-1", member_id=SENDER, heartbeat_at=NOW - STALE),
        _session("dead-2", member_id=THIRD, heartbeat_at=NOW - 2 * STALE),
        _session("alive", member_id=SENDER),
    )

    with store.write() as transaction:
        heartbeat(transaction, _session("beating", member_id=ADDRESSEE), STALE_SECONDS)

    with store.read() as transaction:
        ids = [row[0] for row in transaction.execute("SELECT session_id FROM sessions")]
    assert sorted(ids) == ["alive", "beating"]


def test_deleting_an_unknown_session_is_a_no_op(store: Store) -> None:
    _write(store, _session("s1"))

    with store.write() as transaction:
        delete_session(transaction, "never-written")
    assert count_sessions(store) == 1

    with store.write() as transaction:
        delete_session(transaction, "s1")
    assert count_sessions(store) == 0
