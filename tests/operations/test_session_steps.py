"""The session_tick step: the row and the due rule (slice 263, D2, D5)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store.message_support import NOW

from amoeba.operations.steps.dispatch import StepDocumentError, StepEdges, run_step
from amoeba.store.store import Store
from amoeba.wire.times import DOOR_VERSION
from operations.message_support import (
    RECIPIENT,
    RECIPIENT_NAME,
    THIRD,
    open_message_store,
)
from operations.session_steps_rig import (
    CLIENT_VERSION,
    CONFIG,
    HEARTBEAT,
    SESSION_ID,
    STALE,
    row_of,
    run_tick,
    seed_row,
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    yield from open_message_store(tmp_path)


def test_a_first_tick_writes_the_row_with_the_hubs_time_and_versions(
    store: Store,
) -> None:
    reply = run_tick(store)

    row = row_of(store)
    assert row is not None
    assert (row.member_id, row.started_at, row.heartbeat_at) == (RECIPIENT, NOW, NOW)
    assert (row.client_version, row.door_version) == (CLIENT_VERSION, DOOR_VERSION)
    assert (reply.member_id, reply.member_name) == (RECIPIENT, RECIPIENT_NAME)
    assert reply.notify_poll_seconds == CONFIG.notify_poll_seconds


def test_a_tick_with_nothing_due_changes_no_row_of(store: Store) -> None:
    run_tick(store)

    run_tick(store, NOW + HEARTBEAT - timedelta(seconds=1))

    row = row_of(store)
    assert row is not None
    assert row.heartbeat_at == NOW


def test_a_tick_refreshes_the_row_when_its_heartbeat_is_that_old(store: Store) -> None:
    run_tick(store)

    later = NOW + HEARTBEAT
    run_tick(store, later)

    row = row_of(store)
    assert row is not None
    assert (row.started_at, row.heartbeat_at) == (NOW, later)


def test_a_changed_member_makes_the_tick_write_the_row_again(store: Store) -> None:
    run_tick(store)

    run_tick(store, NOW + timedelta(seconds=1), project_id=THIRD)

    row = row_of(store)
    assert row is not None
    assert (row.member_id, row.heartbeat_at) == (THIRD, NOW + timedelta(seconds=1))


def test_a_new_push_confirmation_makes_the_tick_write_and_stays(store: Store) -> None:
    run_tick(store)
    confirmed = NOW + timedelta(seconds=1)

    run_tick(store, confirmed, push_confirmed=True)
    run_tick(store, confirmed + timedelta(seconds=1), push_confirmed=True)

    row = row_of(store)
    assert row is not None
    assert (row.push_confirmed_at, row.heartbeat_at) == (confirmed, confirmed)


def test_a_refresh_deletes_the_stale_rows_of_other_members(store: Store) -> None:
    seed_row(store, NOW - STALE - timedelta(seconds=1), session_id="b" * 32)
    seed_row(store, NOW - timedelta(seconds=5), session_id="c" * 32, member_id=THIRD)

    run_tick(store)

    assert row_of(store, "b" * 32) is None
    assert row_of(store, "c" * 32) is not None
    assert row_of(store) is not None


def test_a_client_clock_an_hour_ahead_changes_nothing_stored(store: Store) -> None:
    document = {
        "here": {"project_id": RECIPIENT},
        "session_id": SESSION_ID,
        "client": "claude-code",
        "directory": "/work",
        "client_version": CLIENT_VERSION,
        "last_seen": None,
        "push_confirmed": False,
        "client_time": (NOW + timedelta(hours=1)).isoformat(),
    }
    with pytest.raises(StepDocumentError, match="client_time"):
        run_step(
            "session_tick", store, document, StepEdges(lambda: NOW, lambda: CONFIG)
        )
    run_tick(store)

    row = row_of(store)
    assert row is not None
    assert row.heartbeat_at == NOW


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("client", "has/slash"),
        ("client", ""),
        ("directory", ""),
        ("directory", "/work\nsecond line"),
        ("directory", "/" + "d" * 5000),
    ],
)
def test_a_tick_with_a_bad_client_or_directory_is_refused_and_writes_nothing(
    store: Store, field: str, value: str
) -> None:
    document = {
        "here": {"project_id": RECIPIENT},
        "session_id": SESSION_ID,
        "client": "claude-code",
        "directory": "/work",
        "client_version": CLIENT_VERSION,
        "last_seen": None,
        "push_confirmed": False,
        field: value,
    }

    with pytest.raises(StepDocumentError, match=field):
        run_step(
            "session_tick", store, document, StepEdges(lambda: NOW, lambda: CONFIG)
        )

    assert row_of(store) is None
