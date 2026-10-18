"""The real-server harness: a listing read through uvicorn on a loopback port."""

from __future__ import annotations

import threading
from pathlib import Path

import httpx2
from inspection_harness import PROJECT, SeededStore
from serve_harness import SERVER_THREAD_PREFIX, SseEvent, running_server, sse_events

from amoeba.serve.app import build_app
from amoeba.serve.settings import ServeSettings


def _harness_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name.startswith(SERVER_THREAD_PREFIX)]


def test_a_listing_read_through_a_running_server(
    scratch_dir: Path, seeded: SeededStore
) -> None:
    app = build_app(ServeSettings(), None, scratch_dir)

    with running_server(app) as base_url:
        response = httpx2.get(
            f"{base_url}/v1/listings/nodes", params={"project": PROJECT}, timeout=5.0
        )

    assert response.status_code == 200
    assert len(response.json()["rows"]) == 2
    assert _harness_threads() == []


def test_sse_events_splits_frames_on_blank_lines() -> None:
    lines = iter(
        ["id: 3", "event: change", 'data: {"seq":3}', "", ": keepalive", "", ""]
    )

    assert list(sse_events(lines)) == [
        SseEvent(id="3", event="change", data='{"seq":3}'),
        SseEvent(comment="keepalive"),
    ]
