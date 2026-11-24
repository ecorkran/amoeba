"""``send`` writes the wake mark in its own transaction (slice 262, D8 rule 1)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store.message_support import NOW
from store.wake_support import confirmed_session

from amoeba.operations.message_models import SendOutcome
from amoeba.operations.steps.limits import wake_limits
from amoeba.store.store import Store
from amoeba.store.wakes import wake_due
from operations.message_support import RECIPIENT, open_message_store
from operations.wake_send_support import (
    TICK,
    WakeRig,
    at,
    give_command,
    send_request,
    wake_config,
    wake_rig,
)

MARKED = "SELECT wake_wanted_at FROM messages WHERE message_id = ?"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    for opened in open_message_store(tmp_path):
        give_command(opened)
        yield opened


@pytest.fixture
def rig(tmp_path: Path) -> WakeRig:
    return wake_rig(tmp_path)


def _mark(store: Store, request_id: str) -> str | None:
    with store.read() as transaction:
        row = transaction.execute(MARKED, (request_id,)).fetchone()
    assert row is not None
    return None if row[0] is None else str(row[0])


def test_a_send_that_wants_a_wake_sets_the_mark_to_its_clock(
    store: Store, rig: WakeRig
) -> None:
    send_request(store, rig, "ask")

    assert _mark(store, "ask") == NOW.isoformat()


def test_a_send_while_a_session_is_live_sets_no_mark_so_nothing_wakes_it_later(
    store: Store, rig: WakeRig
) -> None:
    with store.write() as transaction:
        confirmed_session(transaction, RECIPIENT, rig.clock.now)

    send_request(store, rig, "ask")
    with store.write() as transaction:
        transaction.execute("DELETE FROM sessions")
        due = wake_due(
            transaction, RECIPIENT, NOW + timedelta(hours=1), wake_limits(wake_config())
        )

    assert _mark(store, "ask") is None
    assert not due
    assert rig.spawner.calls == []


def test_sent_again_unchanged_once_the_session_is_stale_marks_and_wakes(
    store: Store, rig: WakeRig
) -> None:
    with store.write() as transaction:
        confirmed_session(transaction, RECIPIENT, rig.clock.now)
    send_request(store, rig, "ask")
    assert _mark(store, "ask") is None
    with store.write() as transaction:
        transaction.execute("DELETE FROM sessions")
    at(rig, NOW + TICK)

    again = send_request(store, rig, "ask")

    assert again.outcome is SendOutcome.UNCHANGED
    assert _mark(store, "ask") == (NOW + TICK).isoformat()
    assert len(rig.spawner.calls) == 1
