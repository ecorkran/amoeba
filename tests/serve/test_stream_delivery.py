"""The feed over a real server: every change after the cursor, once, in order."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path

import anyio
import httpx2
import pytest
from inspection_harness import PROJECT, SeededStore
from serve_harness import SseEvent, call_asgi, running_server, sse_events

from amoeba.feed import FeedSettings
from amoeba.serve.app import build_app
from amoeba.serve.settings import ServeSettings
from amoeba.serve.stream import CHANGE_EVENT, ERROR_EVENT
from amoeba.store import NodeKind, Store, sql
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION

HEARTBEAT = 0.3
SETTINGS = ServeSettings(
    heartbeat_interval_seconds=HEARTBEAT,
    feed=FeedSettings(follow_interval_seconds=0.02, feed_batch_size=500),
)
#: Each socket read waits at most this; a frame that never comes fails fast.
READ_TIMEOUT = 5.0
_FEED = f"/v1/projects/{PROJECT}/feed"


@pytest.fixture
def base_url(scratch_dir: Path, seeded: SeededStore) -> Iterator[str]:
    with running_server(build_app(SETTINGS, None, scratch_dir)) as url:
        yield url


@contextmanager
def _feed(
    base_url: str,
    *,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> Generator[tuple[httpx2.Response, Iterator[SseEvent]]]:
    with (
        httpx2.Client(base_url=base_url, timeout=READ_TIMEOUT) as client,
        client.stream("GET", _FEED, params=params, headers=headers) as response,
    ):
        yield response, sse_events(response.iter_lines())


def _next_change(events: Iterator[SseEvent]) -> SseEvent:
    """The next non-comment frame."""
    return next(event for event in events if event.comment is None)


def _commit(seeded: SeededStore, count: int) -> list[int]:
    """Create ``count`` nodes; return the seqs of the changes they produced."""
    with Store.open(seeded.store_file) as store:
        head = store.change_head(PROJECT)
        for _ in range(count):
            store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")
        return [c.seq for c in store.changes(PROJECT, after=head, limit=500)]


def _head(base_url: str) -> int:
    body = httpx2.get(
        f"{base_url}/v1/listings/nodes", params={"project": PROJECT}
    ).json()
    return int(body["as_of_seq"])


def _assert_quiet_until_keepalive(events: Iterator[SseEvent]) -> None:
    """No further change arrives before the next keepalive: nothing repeated."""
    event = next(events)
    assert event.comment == "keepalive", event


def test_a_follower_from_as_of_seq_gets_each_new_change_once(
    base_url: str, seeded: SeededStore
) -> None:
    with _feed(base_url, params={"after": str(_head(base_url))}) as (response, events):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        seqs = _commit(seeded, 3)
        received = [_next_change(events) for _ in seqs]
        _assert_quiet_until_keepalive(events)

    assert [event.event for event in received] == [CHANGE_EVENT] * 3
    assert [int(event.id or -1) for event in received] == seqs
    assert [json.loads(event.data or "")["seq"] for event in received] == seqs


@pytest.mark.parametrize("resume_by", ["last-event-id", "after", "both"])
def test_a_reconnect_resumes_with_no_gap_and_no_repeat(
    base_url: str, seeded: SeededStore, resume_by: str
) -> None:
    with _feed(base_url, params={"after": str(_head(base_url))}) as (_, events):
        first = _commit(seeded, 1)
        last = int(_next_change(events).id or -1)
    assert last == first[0]

    away = _commit(seeded, 2)
    params = {"after": str(last)} if resume_by == "after" else None
    headers = None if resume_by == "after" else {"Last-Event-ID": str(last)}
    if resume_by == "both":
        params = {"after": "0"}  # Last-Event-ID wins, or the whole feed repeats

    with _feed(base_url, params=params, headers=headers) as (_, events):
        resumed = [int(_next_change(events).id or -1) for _ in away]
        _assert_quiet_until_keepalive(events)

    assert resumed == away


@pytest.mark.parametrize(
    ("params", "headers"),
    [({"after": "-1"}, None), ({"after": "x"}, None), (None, {"Last-Event-ID": "x"})],
)
def test_a_bad_cursor_is_400(
    base_url: str, params: dict[str, str] | None, headers: dict[str, str] | None
) -> None:
    response = httpx2.get(f"{base_url}{_FEED}", params=params, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_cursor"


def test_an_unknown_project_is_404_before_any_stream(base_url: str) -> None:
    response = httpx2.get(f"{base_url}/v1/projects/never-existed/feed")

    assert response.status_code == 404
    assert response.json()["error"] == "unknown_project"


def test_a_schema_mismatch_is_503_before_any_stream(
    base_url: str, seeded: SeededStore
) -> None:
    connection = sqlite3.connect(seeded.store_file)
    try:
        connection.execute(
            sql.UPSERT_SCHEMA_VERSION,
            (sql.SCHEMA_META_ROW_ID, EXPECTED_SCHEMA_VERSION + 1),
        )
        connection.commit()
    finally:
        connection.close()

    response = httpx2.get(f"{base_url}{_FEED}")

    assert response.status_code == 503
    assert response.json()["error"] == "store_schema_mismatch"


@pytest.mark.parametrize("segment", [".", ".."])
def test_a_dot_project_segment_is_400_and_opens_nothing(
    scratch_dir: Path,
    seeded: SeededStore,
    monkeypatch: pytest.MonkeyPatch,
    segment: str,
) -> None:
    opened: list[object] = []

    def record_open(*args: object, **kwargs: object) -> None:
        opened.append(args)

    monkeypatch.setattr(Store, "open_read_only", record_open)
    app = build_app(SETTINGS, None, scratch_dir)

    exchange = anyio.run(lambda: call_asgi(app, "GET", f"/v1/projects/{segment}/feed"))

    assert exchange.status == 400
    assert json.loads(exchange.body)["error"] == "invalid_project_id"
    assert opened == []


def test_an_encoded_slash_matches_no_route(base_url: str) -> None:
    assert httpx2.get(f"{base_url}/v1/projects/a%2Fb/feed").status_code == 404


def test_a_store_deleted_mid_stream_sends_one_error_and_ends(
    base_url: str, seeded: SeededStore
) -> None:
    with _feed(base_url, params={"after": str(_head(base_url))}) as (_, events):
        assert next(events).comment == "keepalive"  # the stream is up
        for path in seeded.store_file.parent.glob(f"{seeded.store_file.name}*"):
            path.unlink()
        rest = [event for event in events if event.comment is None]

    assert len(rest) == 1
    assert rest[0].event == ERROR_EVENT
    assert json.loads(rest[0].data or "")["error"] == "store_unreadable"


def test_an_idle_stream_sends_a_keepalive_within_one_heartbeat(
    base_url: str, seeded: SeededStore
) -> None:
    with _feed(base_url, params={"after": str(_head(base_url))}) as (_, events):
        started = time.monotonic()
        first = next(events)
        elapsed = time.monotonic() - started

    assert first.comment == "keepalive"
    assert elapsed < HEARTBEAT + 0.5
