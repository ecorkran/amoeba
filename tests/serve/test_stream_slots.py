"""Stream slots and threads are freed on every exit; uvicorn's behaviors pinned."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx2
import pytest
from inspection_harness import PROJECT, SeededStore
from serve_harness import running_server
from starlette.types import Receive, Scope, Send

from amoeba.feed import FeedSettings
from amoeba.serve import feed_route, stream
from amoeba.serve.app import build_app
from amoeba.serve.settings import ServeSettings
from amoeba.serve.stream import FOLLOW_THREAD_PREFIX
from amoeba.store import Change, NodeKind, Store

HEARTBEAT = 0.3
FOLLOW_INTERVAL = 0.02
SEND_TIMEOUT = 1.5
#: Every wait is bounded by this; reaching it fails the test, never hangs it.
DEADLINE = 10.0
_FEED = f"/v1/projects/{PROJECT}/feed"


def _settings(max_streams: int, heartbeat: float = HEARTBEAT) -> ServeSettings:
    return ServeSettings(
        heartbeat_interval_seconds=heartbeat,
        send_timeout_seconds=SEND_TIMEOUT,
        max_streams=max_streams,
        feed=FeedSettings(follow_interval_seconds=FOLLOW_INTERVAL, feed_batch_size=500),
    )


def _follow_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name.startswith(FOLLOW_THREAD_PREFIX)]


def _wait_until(condition: Callable[[], bool], within: float = DEADLINE) -> float:
    """Poll until ``condition`` holds; return how long it took, or fail."""
    started = time.monotonic()
    while not condition():
        if time.monotonic() - started > within:
            raise AssertionError(f"not true within {within}s")
        time.sleep(0.01)
    return time.monotonic() - started


def _stream_status(base_url: str) -> int:
    """Open a stream, note its status, and close it at once."""
    with (
        httpx2.Client(base_url=base_url, timeout=5.0) as client,
        client.stream("GET", _FEED) as response,
    ):
        return response.status_code


@pytest.fixture
def two_slot_server(scratch_dir: Path, seeded: SeededStore) -> Iterator[str]:
    with running_server(build_app(_settings(max_streams=2), None, scratch_dir)) as url:
        yield url


def test_the_third_stream_is_refused_and_reads_still_work(two_slot_server: str) -> None:
    with (
        httpx2.Client(base_url=two_slot_server, timeout=5.0) as client,
        client.stream("GET", _FEED) as first,
        client.stream("GET", _FEED) as second,
    ):
        assert (first.status_code, second.status_code) == (200, 200)
        third = client.get(_FEED)
        read = client.get("/v1/listings/nodes", params={"project": PROJECT})

    assert third.status_code == 503
    assert third.json()["error"] == "stream_limit_reached"
    assert "retry-after" in third.headers
    assert read.status_code == 200


def test_an_abrupt_close_frees_the_slot_and_ends_the_thread(
    two_slot_server: str,
) -> None:
    host, port = two_slot_server.removeprefix("http://").split(":")
    raw = [socket.create_connection((host, int(port))) for _ in range(2)]
    request = f"GET {_FEED} HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n".encode()
    for client in raw:
        client.sendall(request)
    _wait_until(lambda: len(_follow_threads()) == 2)
    assert _stream_status(two_slot_server) == 503

    for client in raw:
        client.close()
    freed_in = _wait_until(lambda: _follow_threads() == [])

    assert freed_in < HEARTBEAT + FOLLOW_INTERVAL + 0.5
    assert _stream_status(two_slot_server) == 200


def test_a_stalled_reader_is_bounded_then_dropped(
    scratch_dir: Path, seeded: SeededStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pins behavior 1: a stalled peer blocks the send; server memory stays flat."""
    committed = 8000
    with Store.open(seeded.store_file) as store:
        for _ in range(committed):
            store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")
    framed: list[int] = []
    real_frame = stream.change_frame

    def counting_frame(change: Change) -> bytes:
        framed.append(change.seq)
        return real_frame(change)

    monkeypatch.setattr(stream, "change_frame", counting_frame)

    with running_server(build_app(_settings(max_streams=1), None, scratch_dir)) as url:
        host, port = url.removeprefix("http://").split(":")
        stalled = socket.socket()
        stalled.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        stalled.connect((host, int(port)))
        stalled.sendall(f"GET {_FEED} HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n".encode())
        try:
            # The hand-off stops advancing well before the timeout fires.
            _wait_until(lambda: len(framed) > 0)
            time.sleep(0.5)
            settled = len(framed)
            time.sleep(0.3)
            assert len(framed) == settled, "the stream kept framing a stalled peer"
            assert settled < committed // 2
            assert len(_follow_threads()) == 1

            freed_in = _wait_until(lambda: _follow_threads() == [])
            assert freed_in < HEARTBEAT + SEND_TIMEOUT + 0.5
            assert _stream_status(url) == 200
        finally:
            stalled.close()


def test_shutdown_with_an_open_stream_stops_the_server_and_the_thread(
    scratch_dir: Path, seeded: SeededStore
) -> None:
    with running_server(build_app(_settings(max_streams=2), None, scratch_dir)) as url:
        host, port = url.removeprefix("http://").split(":")
        client = socket.create_connection((host, int(port)))
        client.sendall(f"GET {_FEED} HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n".encode())
        _wait_until(lambda: len(_follow_threads()) == 1)
    # running_server joined its thread, so the server has stopped.
    try:
        _wait_until(lambda: _follow_threads() == [], within=FOLLOW_INTERVAL + 2.0)
    finally:
        client.close()


def test_a_clean_close_frees_the_slot_without_waiting_for_a_send(
    scratch_dir: Path, seeded: SeededStore
) -> None:
    """With a 30 s heartbeat, no send happens; the slot frees on the disconnect."""
    app = build_app(_settings(max_streams=1, heartbeat=30.0), None, scratch_dir)
    with running_server(app) as url:
        assert _stream_status(url) == 200
        freed_in = _wait_until(lambda: _follow_threads() == [])
        assert freed_in < 2.0
        assert _stream_status(url) == 200


def test_a_failed_thread_start_frees_the_slot(
    scratch_dir: Path, seeded: SeededStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Thread exhaustion is what ``max_streams`` guards; it must not leak a slot."""

    def exhausted(*_: object) -> None:
        raise RuntimeError("can't start new thread")

    app = build_app(_settings(max_streams=1), None, scratch_dir)
    with running_server(app) as url:
        with monkeypatch.context() as patched:
            patched.setattr(feed_route, "start_follow_thread", exhausted)
            with httpx2.Client(base_url=url, timeout=5.0) as client:
                failed = client.get(_FEED)
        assert failed.status_code == 500
        assert _stream_status(url) == 200


def test_uvicorn_reports_a_disconnect_on_receive_and_not_on_send() -> None:
    """Pins behavior 2, which D6's disconnect handling relies on.

    uvicorn 0.54 (h11, ASGI spec 2.3) returns ``http.disconnect`` from
    ``receive()`` once the client goes, and a send after that silently
    succeeds. If this fails because a send raised, uvicorn moved to spec 2.4
    behavior: the server has not regressed, but revisit D6 in the LLD.
    """
    seen: list[str] = []
    done = threading.Event()

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return
        seen.append(f"spec {scope['asgi'].get('spec_version')}")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        while (await receive())["type"] != "http.disconnect":
            pass
        seen.append("disconnect")
        try:
            await send({"type": "http.response.body", "body": b"x", "more_body": True})
            seen.append("send ok")
        except OSError:
            seen.append("send raised")
        done.set()

    with running_server(app) as url:
        host, port = url.removeprefix("http://").split(":")
        client = socket.create_connection((host, int(port)))
        client.sendall(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        time.sleep(0.1)
        client.close()
        assert done.wait(DEADLINE)

    assert seen == ["spec 2.3", "disconnect", "send ok"]
