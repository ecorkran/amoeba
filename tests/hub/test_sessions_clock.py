"""A session's row against the hub's clock: the timings the three checks allow keep a
ticking session live, and a laptop that slept is listed again from its next tick
(slice 263, 8.2, D5, D6). The hub's clock is the one the test sets."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from store.decision_support import CORE
from user_configs import user_config

from amoeba.operations.here_document import HereCaller
from amoeba.operations.steps.models_session import SessionTickRequest
from amoeba.store.models import Session
from amoeba.store.sessions import live_sessions
from amoeba.wire.protocol import (
    HEADER_SESSION_CLIENT,
    HEADER_SESSION_DIRECTORY,
    HEADER_SESSION_ID,
    HEADER_SESSION_PROJECT,
    DoneReply,
)
from hub.call_support import HubRig, build_rig, result_of

SESSION = "cd" * 16
HEARTBEAT, POLL, STALE = 5.0, 5.0, 15.0
HEADERS = {
    HEADER_SESSION_ID: SESSION,
    HEADER_SESSION_PROJECT: CORE,
    HEADER_SESSION_CLIENT: "claude-code",
    HEADER_SESSION_DIRECTORY: "/work/core",
}


@pytest.fixture
def rig(tmp_path: Path) -> HubRig:
    built = build_rig(tmp_path)
    timings = {
        "notify_poll_seconds": POLL,
        "session_heartbeat_seconds": HEARTBEAT,
        "session_stale_seconds": STALE,
    }
    built.config = lambda: user_config().model_copy(update=timings)
    return built


def _tick(rig: HubRig) -> None:
    request = SessionTickRequest(
        here=HereCaller(project_id=CORE),
        session_id=SESSION,
        client="claude-code",
        directory="/work/core",
        last_seen=None,
        push_confirmed=False,
    )
    reply = result_of(
        rig.call("session_tick", request.model_dump(mode="json"), headers=HEADERS)
    )
    assert isinstance(reply, DoneReply), reply


def _live(rig: HubRig) -> tuple[Session, ...]:
    with rig.open_store() as store, store.read() as transaction:
        return live_sessions(transaction, rig.clock(), STALE)


@pytest.mark.parametrize("interval", [POLL, POLL - 0.1], ids=["on-poll", "just-under"])
def test_a_session_ticking_every_poll_interval_is_live_at_every_tick(
    rig: HubRig, interval: float
) -> None:
    _tick(rig)
    for _ in range(12):
        rig.advance(seconds=interval)
        assert len(_live(rig)) == 1, f"gone before the tick at {rig.clock()}"
        _tick(rig)
        assert len(_live(rig)) == 1


def test_a_laptop_that_slept_is_listed_again_at_its_next_tick_as_up_since_then(
    rig: HubRig,
) -> None:
    _tick(rig)
    (first,) = _live(rig)

    rig.advance(hours=1)
    assert _live(rig) == ()
    _tick(rig)

    (again,) = _live(rig)
    assert again.session_id == first.session_id
    assert again.started_at == rig.clock()
    assert again.started_at - first.started_at == timedelta(hours=1)
