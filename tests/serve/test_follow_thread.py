"""The follow thread: ``follow()`` bridged to the loop through a 1-slot hand-off."""

from __future__ import annotations

import threading
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import anyio
import anyio.to_thread
from anyio.streams.memory import MemoryObjectReceiveStream

from amoeba.feed import FeedSettings
from amoeba.serve.errors import ApiErrorCode
from amoeba.serve.stream import (
    FOLLOW_THREAD_PREFIX,
    FollowRequest,
    StreamError,
    StreamItem,
    start_follow_thread,
)
from amoeba.store import Change, NodeKind, Store
from amoeba.store.paths import project_store_path

PROJECT = "demo"
FOLLOW_INTERVAL = 0.05
FAST = FeedSettings(follow_interval_seconds=FOLLOW_INTERVAL, feed_batch_size=500)
#: Every wait is bounded by this; reaching it fails the test rather than hanging.
DEADLINE = 5.0

type _Body = Callable[
    [MemoryObjectReceiveStream[StreamItem], threading.Event, threading.Thread],
    Awaitable[None],
]


def _commit_nodes(scratch_dir: Path, count: int) -> list[int]:
    """Create ``count`` nodes; return the feed seqs they produced."""
    with Store.open(project_store_path(scratch_dir, PROJECT)) as store:
        for _ in range(count):
            store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")
        return [change.seq for change in store.changes(PROJECT, limit=500)]


def _run(scratch_dir: Path, after: int, body: _Body) -> threading.Thread:
    """Start the thread on a fresh loop, run ``body``, and join the thread."""

    async def main() -> threading.Thread:
        send, receive = anyio.create_memory_object_stream[StreamItem](1)
        stop = threading.Event()
        request = FollowRequest(scratch_dir, PROJECT, after, FAST)
        thread = start_follow_thread(request, send, stop)
        try:
            with anyio.fail_after(DEADLINE):
                await body(receive, stop, thread)
        finally:
            stop.set()
            send.close()  # as the stream's on_close does, on the loop
            receive.close()
            await anyio.to_thread.run_sync(thread.join, DEADLINE)
        return thread

    thread = anyio.run(main)
    assert not thread.is_alive(), "the follow thread outlived its stream"
    return thread


def test_changes_arrive_in_seq_order_from_the_cursor(scratch_dir: Path) -> None:
    seqs = _commit_nodes(scratch_dir, 5)
    received: list[int] = []

    async def body(
        items: MemoryObjectReceiveStream[StreamItem],
        stop: threading.Event,
        thread: threading.Thread,
    ) -> None:
        for _ in range(3):
            item = await items.receive()
            assert isinstance(item, Change)
            received.append(item.seq)

    thread = _run(scratch_dir, seqs[1], body)

    assert received == seqs[2:]
    assert thread.name.startswith(FOLLOW_THREAD_PREFIX)


def test_closing_the_receive_side_wakes_a_thread_blocked_in_the_hand_off(
    scratch_dir: Path,
) -> None:
    _commit_nodes(scratch_dir, 3)

    async def body(
        items: MemoryObjectReceiveStream[StreamItem],
        stop: threading.Event,
        thread: threading.Thread,
    ) -> None:
        # One change fills the slot; the thread then blocks handing off the next.
        await anyio.sleep(FOLLOW_INTERVAL * 4)
        assert items.statistics().current_buffer_used == 1
        assert items.statistics().tasks_waiting_send == 1
        items.close()  # stop is deliberately not set
        await anyio.to_thread.run_sync(thread.join, DEADLINE)
        assert not thread.is_alive()

    _run(scratch_dir, 0, body)


def test_the_stop_event_ends_a_thread_waiting_in_follow(scratch_dir: Path) -> None:
    seqs = _commit_nodes(scratch_dir, 1)

    async def body(
        items: MemoryObjectReceiveStream[StreamItem],
        stop: threading.Event,
        thread: threading.Thread,
    ) -> None:
        await anyio.sleep(FOLLOW_INTERVAL * 3)  # idle: nothing after the cursor
        started = time.monotonic()
        stop.set()
        await anyio.to_thread.run_sync(thread.join, DEADLINE)
        assert not thread.is_alive()
        assert time.monotonic() - started < FOLLOW_INTERVAL + 0.5

    _run(scratch_dir, seqs[-1], body)


def test_a_store_deleted_mid_follow_yields_one_error_item(scratch_dir: Path) -> None:
    seqs = _commit_nodes(scratch_dir, 1)
    store_file = project_store_path(scratch_dir, PROJECT)
    items_seen: list[StreamItem] = []

    async def body(
        items: MemoryObjectReceiveStream[StreamItem],
        stop: threading.Event,
        thread: threading.Thread,
    ) -> None:
        await anyio.sleep(FOLLOW_INTERVAL * 2)
        for path in store_file.parent.glob(f"{store_file.name}*"):
            path.unlink()
        items_seen.append(await items.receive())
        await anyio.to_thread.run_sync(thread.join, DEADLINE)
        assert not thread.is_alive(), "the thread did not exit after its error"

    _run(scratch_dir, seqs[-1], body)

    assert len(items_seen) == 1
    error = items_seen[0]
    assert isinstance(error, StreamError)
    assert error.code is ApiErrorCode.STORE_UNREADABLE
