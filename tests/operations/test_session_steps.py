"""``session_tick`` and ``session_end`` on a store (slice 263, D2, D5)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from store.message_support import NOW, TTL
from user_configs import user_config

from amoeba.operations.steps.dispatch import StepDocumentError, StepEdges, run_step
from amoeba.operations.steps.models import STEP_MODELS
from amoeba.operations.steps.models_session import SessionTickReply
from amoeba.operations.steps.session import write_behind_session
from amoeba.program_version import program_version
from amoeba.store.deliveries import write_delivery
from amoeba.store.errors import StoreError
from amoeba.store.machines import (
    ActingMachine,
    invite_machine,
    machine_id_by_name,
)
from amoeba.store.messages import insert_request
from amoeba.store.models import Session
from amoeba.store.sessions import get_session, live_sessions, upsert_session
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent
from amoeba.wire.protocol import (
    CHANNEL_EVENT_MAX_ENTRIES,
    STEP_CALLS,
    WRITING_STEPS,
)
from amoeba.wire.times import DOOR_VERSION, TICK_TIMES
from operations.message_support import (
    RECIPIENT,
    RECIPIENT_NAME,
    SENDER,
    THIRD,
    open_message_store,
)

SESSION_ID = "a" * 32
CONFIG = user_config()
HEARTBEAT = timedelta(seconds=CONFIG.session_heartbeat_seconds)
STALE = timedelta(seconds=CONFIG.session_stale_seconds)
MARKERS = ("MARKER-SUBJECT", "MARKER-BODY", "MARKER-RESULT", "MARKER-REASON")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    yield from open_message_store(tmp_path)


def _tick(
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
        "last_seen": last_seen,
        "push_confirmed": push_confirmed,
    }
    reply = run_step(
        "session_tick", store, document, StepEdges(lambda: now, lambda: CONFIG)
    )
    assert isinstance(reply, SessionTickReply)
    return reply


def _end(store: Store, session_id: str = SESSION_ID) -> None:
    run_step(
        "session_end",
        store,
        {"session_id": session_id},
        StepEdges(lambda: NOW, _no_config),
    )


def _no_config() -> Any:
    raise AssertionError("session_end loads no config")


def _row(store: Store, session_id: str = SESSION_ID) -> Session | None:
    with store.read() as transaction:
        return get_session(transaction, session_id)


def _request(store: Store, number: int, *, to: str = RECIPIENT, text: str = "") -> None:
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


def _seed_row(
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


def test_a_first_tick_writes_the_row_with_the_hubs_time_and_versions(
    store: Store,
) -> None:
    reply = _tick(store)

    row = _row(store)
    assert row is not None
    assert (row.member_id, row.started_at, row.heartbeat_at) == (RECIPIENT, NOW, NOW)
    assert (row.client_version, row.door_version) == (program_version(), DOOR_VERSION)
    assert (reply.member_id, reply.member_name) == (RECIPIENT, RECIPIENT_NAME)
    assert reply.notify_poll_seconds == CONFIG.notify_poll_seconds


def test_a_tick_with_nothing_due_changes_no_row(store: Store) -> None:
    _tick(store)

    _tick(store, NOW + HEARTBEAT - timedelta(seconds=1))

    row = _row(store)
    assert row is not None
    assert row.heartbeat_at == NOW


def test_a_tick_refreshes_the_row_when_its_heartbeat_is_that_old(store: Store) -> None:
    _tick(store)

    later = NOW + HEARTBEAT
    _tick(store, later)

    row = _row(store)
    assert row is not None
    assert (row.started_at, row.heartbeat_at) == (NOW, later)


def test_a_changed_member_makes_the_tick_write_the_row_again(store: Store) -> None:
    _tick(store)

    _tick(store, NOW + timedelta(seconds=1), project_id=THIRD)

    row = _row(store)
    assert row is not None
    assert (row.member_id, row.heartbeat_at) == (THIRD, NOW + timedelta(seconds=1))


def test_a_new_push_confirmation_makes_the_tick_write_and_stays(store: Store) -> None:
    _tick(store)
    confirmed = NOW + timedelta(seconds=1)

    _tick(store, confirmed, push_confirmed=True)
    _tick(store, confirmed + timedelta(seconds=1), push_confirmed=True)

    row = _row(store)
    assert row is not None
    assert (row.push_confirmed_at, row.heartbeat_at) == (confirmed, confirmed)


def test_a_refresh_deletes_the_stale_rows_of_other_members(store: Store) -> None:
    _seed_row(store, NOW - STALE - timedelta(seconds=1), session_id="b" * 32)
    _seed_row(store, NOW - timedelta(seconds=5), session_id="c" * 32, member_id=THIRD)

    _tick(store)

    assert _row(store, "b" * 32) is None
    assert _row(store, "c" * 32) is not None
    assert _row(store) is not None


def test_a_client_clock_an_hour_ahead_changes_nothing_stored(store: Store) -> None:
    document = {
        "here": {"project_id": RECIPIENT},
        "session_id": SESSION_ID,
        "client": "claude-code",
        "directory": "/work",
        "last_seen": None,
        "push_confirmed": False,
        "client_time": (NOW + timedelta(hours=1)).isoformat(),
    }
    with pytest.raises(StepDocumentError, match="client_time"):
        run_step(
            "session_tick", store, document, StepEdges(lambda: NOW, lambda: CONFIG)
        )
    _tick(store)

    row = _row(store)
    assert row is not None
    assert row.heartbeat_at == NOW


def test_no_entries_without_last_seen(store: Store) -> None:
    _request(store, 1)

    reply = _tick(store)

    assert (reply.entries, reply.count, reply.first_seq) == ((), 0, None)
    assert reply.high_seq == 1


def test_a_backlog_lists_ten_with_the_count_and_the_first_number(store: Store) -> None:
    for number in range(1, 14):
        _request(store, number)

    reply = _tick(store, last_seen=2)

    assert reply.count == 11
    assert reply.first_seq == 3
    assert [entry.seq for entry in reply.entries] == list(
        range(3, 3 + CHANNEL_EVENT_MAX_ENTRIES)
    )
    assert reply.high_seq == 13


def test_a_last_seen_at_the_high_number_lists_nothing(store: Store) -> None:
    _request(store, 1)

    reply = _tick(store, last_seen=1)

    assert (reply.entries, reply.count) == ((), 0)


def test_as_of_seq_is_the_highest_number_assigned_to_anyone(store: Store) -> None:
    _request(store, 1)
    _request(store, 2, to=THIRD)

    reply = _tick(store, last_seen=0)

    assert reply.high_seq == 1
    assert reply.as_of_seq == 2


def test_no_message_text_is_in_a_reply(store: Store) -> None:
    for number, marker in enumerate(MARKERS, start=1):
        _request(store, number, text=marker)

    reply = _tick(store, last_seen=0)

    assert reply.entries
    document = reply.model_dump_json()
    assert not [marker for marker in MARKERS if marker in document]


def test_a_non_member_deletes_the_row_and_gets_the_reason(store: Store) -> None:
    _tick(store)

    reply = _tick(store, here={"not_a_project": "not in a project"})

    assert reply.member_id is None
    assert reply.reason
    assert _row(store) is None
    assert (reply.high_seq, reply.count, reply.as_of_seq) == (0, 0, 0)


def test_a_session_id_on_another_machine_fails_with_a_store_error(
    store: Store,
) -> None:
    with store.write() as transaction:
        invite_machine(transaction, "beta", "0" * 64, NOW)
        beta = machine_id_by_name(transaction, "beta")
        local = transaction.acting("sessions")
    assert beta is not None
    store.act_as(ActingMachine(beta, local.owner_id))
    _seed_row(store, NOW - HEARTBEAT)
    store.act_as(local)

    with pytest.raises(StoreError, match="another machine"):
        _tick(store, NOW)
    _end(store)

    assert _row(store) is not None


def test_session_end_deletes_the_row_and_ignores_a_missing_id(store: Store) -> None:
    _tick(store)

    _end(store)
    _end(store)

    assert _row(store) is None


def test_a_row_written_after_the_end_is_not_live_after_the_stale_time(
    store: Store,
) -> None:
    _tick(store)
    _end(store)
    _tick(store, NOW + timedelta(seconds=1))

    later = NOW + timedelta(seconds=1) + STALE
    with store.read() as transaction:
        assert live_sessions(transaction, later, CONFIG.session_stale_seconds) == ()
    _tick(store, later, session_id="d" * 32)

    assert _row(store) is None


def test_the_tick_has_no_retry_and_both_steps_keep_no_result() -> None:
    assert TICK_TIMES.retry_seconds == 0
    for name in ("session_tick", "session_end"):
        step = STEP_MODELS[name]
        assert name in STEP_CALLS
        assert name not in WRITING_STEPS
        assert (step.writes, step.keeps_result) == (True, False)
    assert STEP_MODELS["session_tick"].needs_config
    assert not STEP_MODELS["session_end"].needs_config


def test_both_steps_run_in_a_write_transaction(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    counts = {"reads": 0, "writes": 0}
    real_read, real_write = store.read, store.write

    def read() -> Any:
        counts["reads"] += 1
        return real_read()

    def write() -> Any:
        counts["writes"] += 1
        return real_write()

    monkeypatch.setattr(store, "read", read)
    monkeypatch.setattr(store, "write", write)

    _tick(store)
    _end(store)

    assert counts == {"reads": 0, "writes": 2}


def test_the_hub_clock_alone_dates_the_row(store: Store) -> None:
    _tick(store, datetime(2026, 1, 1, tzinfo=UTC))

    row = _row(store)
    assert row is not None
    assert row.heartbeat_at == datetime(2026, 1, 1, tzinfo=UTC)


def test_a_refused_session_gets_a_row_with_the_callers_versions(store: Store) -> None:
    with store.write() as transaction:
        write_behind_session(
            transaction, NOW, RECIPIENT, SESSION_ID, "claude-code", "/work", "0.9.0", 1
        )
    later = NOW + timedelta(seconds=5)
    with store.write() as transaction:
        write_behind_session(
            transaction,
            later,
            RECIPIENT,
            SESSION_ID,
            "claude-code",
            "/work",
            "0.9.0",
            1,
        )

    row = _row(store)
    assert row is not None
    assert (row.client_version, row.door_version) == ("0.9.0", 1)
    assert (row.started_at, row.heartbeat_at) == (NOW, later)
