"""The session steps: entries, non-members and exit (slice 263, D2, D8)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from store.message_support import NOW

from amoeba.operations.steps.models import STEP_MODELS
from amoeba.operations.steps.session import write_behind_session
from amoeba.store.errors import StoreError
from amoeba.store.machines import (
    ActingMachine,
    invite_machine,
    machine_id_by_name,
)
from amoeba.store.sessions import live_sessions
from amoeba.store.store import Store
from amoeba.wire.protocol import (
    CHANNEL_EVENT_MAX_ENTRIES,
    STEP_CALLS,
    WRITING_STEPS,
)
from amoeba.wire.times import TICK_TIMES
from operations.message_support import (
    RECIPIENT,
    THIRD,
    open_message_store,
)
from operations.session_steps_rig import (
    CONFIG,
    HEARTBEAT,
    MARKERS,
    SESSION_ID,
    STALE,
    end_session,
    request_to,
    row_of,
    run_tick,
    seed_row,
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    yield from open_message_store(tmp_path)


def test_no_entries_without_last_seen(store: Store) -> None:
    request_to(store, 1)

    reply = run_tick(store)

    assert (reply.entries, reply.count, reply.first_seq) == ((), 0, None)
    assert reply.high_seq == 1


def test_a_backlog_lists_ten_with_the_count_and_the_first_number(store: Store) -> None:
    for number in range(1, 14):
        request_to(store, number)

    reply = run_tick(store, last_seen=2)

    assert reply.count == 11
    assert reply.first_seq == 3
    assert [entry.seq for entry in reply.entries] == list(
        range(3, 3 + CHANNEL_EVENT_MAX_ENTRIES)
    )
    assert reply.high_seq == 13


def test_a_last_seen_at_the_high_number_lists_nothing(store: Store) -> None:
    request_to(store, 1)

    reply = run_tick(store, last_seen=1)

    assert (reply.entries, reply.count) == ((), 0)


def test_as_of_seq_is_the_highest_number_assigned_to_anyone(store: Store) -> None:
    request_to(store, 1)
    request_to(store, 2, to=THIRD)

    reply = run_tick(store, last_seen=0)

    assert reply.high_seq == 1
    assert reply.as_of_seq == 2


def test_no_message_text_is_in_a_reply(store: Store) -> None:
    for number, marker in enumerate(MARKERS, start=1):
        request_to(store, number, text=marker)

    reply = run_tick(store, last_seen=0)

    assert reply.entries
    document = reply.model_dump_json()
    assert not [marker for marker in MARKERS if marker in document]


def test_a_non_member_deletes_the_row_and_gets_the_reason(store: Store) -> None:
    run_tick(store)

    reply = run_tick(store, here={"not_a_project": "not in a project"})

    assert reply.member_id is None
    assert reply.reason
    assert row_of(store) is None
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
    seed_row(store, NOW - HEARTBEAT)
    store.act_as(local)

    with pytest.raises(StoreError, match="another machine"):
        run_tick(store, NOW)
    end_session(store)

    assert row_of(store) is not None


def test_session_end_deletes_the_row_and_ignores_a_missing_id(store: Store) -> None:
    run_tick(store)

    end_session(store)
    end_session(store)

    assert row_of(store) is None


def test_a_row_written_after_the_end_is_not_live_after_the_stale_time(
    store: Store,
) -> None:
    run_tick(store)
    end_session(store)
    run_tick(store, NOW + timedelta(seconds=1))

    later = NOW + timedelta(seconds=1) + STALE
    with store.read() as transaction:
        assert live_sessions(transaction, later, CONFIG.session_stale_seconds) == ()
    run_tick(store, later, session_id="d" * 32)

    assert row_of(store) is None


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

    run_tick(store)
    end_session(store)

    assert counts == {"reads": 0, "writes": 2}


def test_the_hub_clock_alone_dates_the_row_of(store: Store) -> None:
    run_tick(store, datetime(2026, 1, 1, tzinfo=UTC))

    row = row_of(store)
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

    row = row_of(store)
    assert row is not None
    assert (row.client_version, row.door_version) == ("0.9.0", 1)
    assert (row.started_at, row.heartbeat_at) == (NOW, later)
