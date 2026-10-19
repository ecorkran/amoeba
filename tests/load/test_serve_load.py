"""Load tier for slice 109: 32 followers over a real uvicorn on loopback.

**Delivery.** 32 followers stream the feed while one writer commits a burst of
``BURST`` intents as fast as it can. 600 passes one ``feed_batch_size`` (500),
so the burst crosses a batch boundary, where loss or reordering would show.
Every follower must receive every change, once, in ``seq`` order. The time to
drain the burst is printed, not asserted: it is throughput, which the network
contract does not promise.

**Latency.** The same 32 followers while ``BURST`` changes are committed at a
steady ``PACED_RATE`` per second. The p95 commit-to-arrival time must be at
most 1 s: 106's bound (``follow_interval_seconds`` plus the read) with room for
the hand-off and loopback transport.

**No starvation.** With 32 idle streams holding their threads, a listing read
still succeeds. No read latency is promised, so none is asserted.

Measured 20261018 on the development machine (Darwin 25.5.0, Python 3.13), with
the 32 clients in the same process as the server:

    600-change burst (committed in 60 ms), drained to all 32   2.7 s
    600 changes at 100/s, p95 commit-to-arrival               0.234 s  (bound 1 s)

A burst therefore drains at about 7,000 frames/s for the whole process: one
hand-off per change per stream. Handing off batches is the fix if a consumer
ever needs bursts delivered faster; it is not needed now (PM, 20261018).
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import httpx2
import pytest
from feed_harness import post_intent
from load_harness import measured
from serve_harness import running_server, sse_events

from amoeba.feed import FeedSettings
from amoeba.serve.app import build_app
from amoeba.serve.settings import ServeSettings
from amoeba.serve.stream import FOLLOW_THREAD_PREFIX
from amoeba.store import NodeKind, Store
from amoeba.store.paths import project_store_path

PROJECT = "load"
FOLLOWERS = 32
BURST = 600
#: Commits per second in the latency test: steady, not a burst.
PACED_RATE = 100
P95_BOUND_SECONDS = 1.0
#: Every wait is bounded by this; reaching it fails the test, never hangs it.
DEADLINE_SECONDS = 60.0
SETTINGS = ServeSettings(max_streams=FOLLOWERS)


@dataclass
class _Follower:
    """One client's view: when each seq arrived."""

    arrivals: dict[int, float] = field(default_factory=dict[int, float])
    order: list[int] = field(default_factory=list[int])
    error: str | None = None


def _follow_threads() -> int:
    return sum(t.name.startswith(FOLLOW_THREAD_PREFIX) for t in threading.enumerate())


def _wait_for(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + DEADLINE_SECONDS
    while not condition():
        assert time.monotonic() < deadline, f"{what} did not happen"
        time.sleep(0.01)


@pytest.fixture
def node(supervisor_dir: Path) -> str:
    with Store.open(project_store_path(supervisor_dir, PROJECT)) as store:
        return store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n").id


@pytest.fixture
def base_url(supervisor_dir: Path, node: str) -> Iterator[str]:
    with running_server(build_app(SETTINGS, None, supervisor_dir)) as url:
        yield url


def _head(supervisor_dir: Path) -> int:
    with Store.open_read_only(project_store_path(supervisor_dir, PROJECT)) as store:
        return store.change_head(PROJECT)


def _follow(base_url: str, after: int, last: list[int], into: _Follower) -> None:
    """Read until the seq in ``last`` (set once the burst ends) arrives."""
    try:
        with (
            httpx2.Client(base_url=base_url, timeout=DEADLINE_SECONDS) as client,
            client.stream(
                "GET", f"/v1/projects/{PROJECT}/feed", params={"after": str(after)}
            ) as response,
        ):
            for event in sse_events(response.iter_lines()):
                if event.id is None:
                    continue
                seq = int(event.id)
                into.arrivals[seq] = time.monotonic()
                into.order.append(seq)
                if last and seq >= last[0]:
                    return
    except httpx2.HTTPError as error:
        # Specific: recorded and asserted on by the test thread.
        into.error = repr(error)


def _p95(values: list[float]) -> float:
    ranked = sorted(values)
    return ranked[math.ceil(0.95 * len(ranked)) - 1]


@dataclass(frozen=True)
class _Run:
    """What one followed write produced: the seqs, and when each committed."""

    expected: list[int]
    committed_at: dict[int, float]
    followers: list[_Follower]


def _followed_write(
    supervisor_dir: Path, base_url: str, node: str, *, pause_seconds: float
) -> _Run:
    """``FOLLOWERS`` streams open, then ``BURST`` intents with a pause between."""
    start = _head(supervisor_dir)
    last: list[int] = []
    followers = [_Follower() for _ in range(FOLLOWERS)]
    threads = [
        threading.Thread(target=_follow, args=(base_url, start, last, f), daemon=True)
        for f in followers
    ]
    for thread in threads:
        thread.start()
    _wait_for(lambda: _follow_threads() == FOLLOWERS, "all streams open")

    committed_at: dict[int, float] = {}
    with Store.open(project_store_path(supervisor_dir, PROJECT)) as writer:
        head = start
        for index in range(BURST):
            post_intent(writer, f"load-{index}", node, PROJECT)
            now = time.monotonic()
            new_head = writer.change_head(PROJECT)
            committed_at.update(dict.fromkeys(range(head + 1, new_head + 1), now))
            head = new_head
            if pause_seconds:
                time.sleep(pause_seconds)
        expected = [
            c.seq for c in writer.changes(PROJECT, after=start, limit=10 * BURST)
        ]
    last.append(head)

    for thread in threads:
        thread.join(DEADLINE_SECONDS)
        assert not thread.is_alive(), "a follower never received the last change"
    for follower in followers:
        assert follower.error is None, follower.error
        assert follower.order == expected, "a follower missed or reordered a change"
    assert len(expected) >= BURST
    return _Run(expected=expected, committed_at=committed_at, followers=followers)


def test_32_followers_receive_a_600_change_burst_in_order(
    supervisor_dir: Path, base_url: str, node: str
) -> None:
    assert SETTINGS.feed == FeedSettings()  # production follow settings

    run = _followed_write(supervisor_dir, base_url, node, pause_seconds=0.0)

    first_commit = min(run.committed_at.values())
    drained = max(max(f.arrivals.values()) for f in run.followers) - first_commit
    print(
        f"burst of {len(run.expected)} drained to {FOLLOWERS} followers "
        f"in {drained:.2f}s"
    )


def test_p95_latency_at_a_steady_rate_is_within_a_second(
    supervisor_dir: Path, base_url: str, node: str
) -> None:
    run = _followed_write(supervisor_dir, base_url, node, pause_seconds=1 / PACED_RATE)

    latencies = [
        follower.arrivals[seq] - run.committed_at[seq]
        for follower in run.followers
        for seq in run.expected
    ]
    p95 = _p95(latencies)
    report = measured("p95 commit-to-arrival", p95, P95_BOUND_SECONDS)
    print(report)
    assert p95 <= P95_BOUND_SECONDS, report


def test_32_idle_streams_do_not_starve_a_read(
    base_url: str, supervisor_dir: Path
) -> None:
    stop = [_head(supervisor_dir) + 10**9]  # never reached: the streams stay idle
    threads = [
        threading.Thread(
            target=_follow,
            args=(base_url, _head(supervisor_dir), stop, _Follower()),
            daemon=True,
        )
        for _ in range(FOLLOWERS)
    ]
    for thread in threads:
        thread.start()
    _wait_for(lambda: _follow_threads() == FOLLOWERS, "all streams open")

    response = httpx2.get(
        f"{base_url}/v1/listings/nodes",
        params={"project": PROJECT},
        timeout=DEADLINE_SECONDS,
    )

    assert response.status_code == 200
    assert len(response.json()["rows"]) == 1
