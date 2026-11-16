"""Presence under load: many servers on one store (slice 241, D2, D6, 9.4).

Twelve presence runs share one throwaway store, each with its own stores opened in
worker threads, as twelve ``amoeba-mcp`` processes would have. A writer thread adds
bursts of deliveries for several of their members while an SDK client makes tool
calls and pings against one of them. The checks are the design's: no heartbeat gap
reaches ``session_stale_seconds``, every burst is one event with the right count,
every answer comes within a second, and nothing ends presence.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Final

import anyio
import pytest
from cf_fixtures import DEFAULT_WORKTREE, fixture_document
from cli.cli_support import write_config
from mcp import ClientSession
from mcp_server.presence_rig import (
    START,
    Opener,
    RecordingOutbound,
    make_connection,
    seed_member,
    sessions_in,
)
from mcp_server.serving_rig import presence_background, serving
from store.message_support import send_request

from amoeba.mcp import presence
from amoeba.mcp.channel_event import CHANNEL_METHOD
from amoeba.mcp.presence import (
    PresenceDeps,
    PresenceState,
    SessionTiming,
    ToolPresence,
)
from amoeba.mcp.presence_task import run_presence
from amoeba.mcp.server import build_server
from amoeba.store.deliveries import write_delivery
from amoeba.store.models import Session
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent
from amoeba.upstream.context_forge.cli_call import CfRun
from amoeba.wiring_presence import StoreOpener, beat_session

PRESENCES: Final = 12
#: Members that get mail; the served one (index 0) gets none, so its client's
#: notifications do not need counting.
BURSTED: Final = range(1, 7)
BURSTS: Final = 3
DELIVERIES_PER_BURST: Final = 2
#: Long enough between bursts that every watcher ticks several times in the gap.
BURST_GAP_SECONDS: Final = 0.6
TIMING: Final = SessionTiming(
    notify_poll_seconds=0.02,
    session_heartbeat_seconds=0.05,
    session_stale_seconds=1.0,
)
ANSWER_BOUND_SECONDS: Final = 1.0
SENDER: Final = "load-sender"
RUN_BUDGET_SECONDS: Final = 60


def _member(index: int) -> str:
    return f"load-member-{index:02d}"


def _cf_run_for(project_id: str) -> CfRun:
    """``cf get`` answering with the recorded project document, under ``project_id``."""
    document = {**fixture_document(DEFAULT_WORKTREE), "id": project_id}
    text = json.dumps(document)

    def run(argv: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(argv), 0, text, "")

    return run


def _wall_clock() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def store_path() -> Path:
    write_config()
    path = Path(os.environ["AMOEBA_HOME"]) / "amoeba.sqlite3"
    seed_member(path, SENDER)
    for index in range(PRESENCES):
        seed_member(path, _member(index))
    return path


def _write_bursts(path: Path, started: threading.Event) -> None:
    """``BURSTS`` bursts, each one transaction of two deliveries per bursted member."""
    started.wait()
    for burst in range(BURSTS):
        time.sleep(BURST_GAP_SECONDS)
        with Store.open(path) as store, store.write() as transaction:
            for index in BURSTED:
                message = f"m-{burst}-{index}"
                send_request(
                    transaction, message, from_member=SENDER, to_member=_member(index)
                )
                for _ in range(DELIVERIES_PER_BURST):
                    write_delivery(
                        transaction, _member(index), message, DeliveryEvent.SENT, START
                    )
    time.sleep(BURST_GAP_SECONDS)


def _deps(path: Path, index: int) -> PresenceDeps:
    return PresenceDeps(
        open_store=Opener(path),
        cf_run=_cf_run_for(_member(index)),
        clock=_wall_clock,
        timing=TIMING,
    )


async def _client_calls(session: ClientSession, until: threading.Event) -> list[float]:
    """Ping, list tools and call a tool, timing each, until ``until`` is set."""
    latencies: list[float] = []
    while not until.is_set():
        for call in (
            session.send_ping,
            session.list_tools,
            partial(session.call_tool, "decisions", {}),
        ):
            started = time.monotonic()
            await call()
            latencies.append(time.monotonic() - started)
        await anyio.sleep(0.05)
    return latencies


def _record_beats(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[datetime]]:
    """Each session's written ``heartbeat_at`` values, in order, as beats succeed."""
    beats: dict[str, list[datetime]] = {}

    def recording(
        open_store: StoreOpener, session: Session, stale_seconds: float
    ) -> None:
        beat_session(open_store, session, stale_seconds)
        beats.setdefault(session.session_id, []).append(session.heartbeat_at)

    monkeypatch.setattr(presence, "beat_session", recording)
    return beats


def test_twelve_presences_on_one_store_under_bursts_and_tool_calls(
    store_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    beats = _record_beats(monkeypatch)
    outbounds = {index: RecordingOutbound() for index in range(1, PRESENCES)}
    latencies: list[float] = []
    started = threading.Event()
    writer_done = threading.Event()

    def writer() -> None:
        _write_bursts(store_path, started)
        writer_done.set()

    async def main() -> None:
        served_deps = _deps(store_path, 0)
        served_state = PresenceState(started_at=_wall_clock())
        server = build_server(
            ToolPresence(served_state, _wall_clock), served_deps.open_store
        )
        thread = threading.Thread(target=writer)
        thread.start()
        with anyio.fail_after(RUN_BUDGET_SECONDS):
            async with anyio.create_task_group() as group:
                for index, outbound in outbounds.items():
                    state = PresenceState(started_at=_wall_clock())
                    connection = make_connection(outbound)
                    connection.initialized.set()
                    group.start_soon(
                        run_presence, connection, state, _deps(store_path, index)
                    )
                background = presence_background(served_state, served_deps)
                async with serving(server, background) as session:
                    started.set()
                    latencies.extend(await _client_calls(session, writer_done))
                    live.extend(
                        await anyio.to_thread.run_sync(
                            sessions_in,
                            store_path,
                            _wall_clock(),
                            TIMING.session_stale_seconds,
                        )
                    )
                group.cancel_scope.cancel()
        await anyio.to_thread.run_sync(thread.join)

    live: list[Session] = []
    with caplog.at_level(logging.WARNING):
        anyio.run(main)

    # No heartbeat gap reached the stale limit; all twelve rows are fresh at the end.
    assert len(beats) == PRESENCES
    largest_gap = max(
        (later - earlier).total_seconds()
        for times in beats.values()
        for earlier, later in zip(times, times[1:], strict=False)
    )
    assert largest_gap < TIMING.session_stale_seconds, f"heartbeat gap {largest_gap}s"
    assert sorted(session.member_id for session in live) == [
        _member(index) for index in range(PRESENCES)
    ]
    for index, outbound in outbounds.items():
        events = [
            params for method, params in outbound.sent if method == CHANNEL_METHOD
        ]
        expected = BURSTS if index in BURSTED else 0
        assert len(events) == expected, f"member {index}: {len(events)} events"
        for event in events:
            meta = event["meta"]
            assert isinstance(meta, dict) and meta["count"] == str(DELIVERIES_PER_BURST)
    assert latencies and max(latencies) < ANSWER_BOUND_SECONDS
    assert not [r for r in caplog.records if "presence stopped" in r.getMessage()]
