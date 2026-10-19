"""``EventStreamResponse`` in-process: framing, heartbeats, timeouts, and closing."""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from types import MappingProxyType

import anyio
import pytest
from anyio.streams.memory import MemoryObjectSendStream
from starlette.types import Message

from amoeba.serve.errors import ApiErrorCode
from amoeba.serve.stream import (
    KEEPALIVE_FRAME,
    EventStreamResponse,
    StreamError,
    StreamItem,
    change_frame,
    error_frame,
)
from amoeba.store import Change
from amoeba.store.feed_models import ChangeKind

#: Every test finishes far inside this; reaching it is a hang, and fails.
_DEADLINE = 5.0
_SCOPE = {"type": "http"}

_CHANGE = Change(
    seq=42,
    project_id="demo",
    kind=ChangeKind.MESSAGE_POSTED,
    node_id=None,
    subject_id="m-1",
    payload=MappingProxyType({"channel": "intent"}),
    recorded_at=datetime(2026, 10, 18, 12, 0, tzinfo=UTC),
)


def test_a_change_frame_is_id_event_data() -> None:
    assert change_frame(_CHANGE) == (
        b"id: 42\nevent: change\n"
        b'data: {"seq": 42, "project_id": "demo", "kind": "message_posted", '
        b'"node_id": null, "subject_id": "m-1", "payload": {"channel": "intent"}, '
        b'"recorded_at": "2026-10-18T12:00:00+00:00"}\n\n'
    )


def test_the_keepalive_is_an_sse_comment() -> None:
    assert KEEPALIVE_FRAME == b": keepalive\n\n"


def test_an_error_frame_carries_the_error_body() -> None:
    frame = error_frame(StreamError(ApiErrorCode.STORE_UNREADABLE, "gone"))

    assert frame == (
        b'event: error\ndata: {"error": "store_unreadable", "detail": "gone"}\n\n'
    )


class _Recorder:
    """A fake ASGI peer: records what is sent; ``receive`` waits for a disconnect."""

    def __init__(self) -> None:
        self.sent: list[Message] = []
        self.closes = 0
        self.disconnect = anyio.Event()

    async def send(self, message: Message) -> None:
        self.sent.append(message)

    async def receive(self) -> Message:
        await self.disconnect.wait()
        return {"type": "http.disconnect"}

    def on_close(self) -> None:
        self.closes += 1

    @property
    def bodies(self) -> list[bytes]:
        return [m["body"] for m in self.sent if m["type"] == "http.response.body"]


type _Driver = Callable[
    [MemoryObjectSendStream[StreamItem], _Recorder], Awaitable[None]
]


def _run(
    drive: _Driver,
    *,
    heartbeat: float = 10.0,
    send_timeout: float = 10.0,
    recorder: _Recorder | None = None,
) -> _Recorder:
    """Run the response against ``recorder`` while ``drive`` feeds its stream."""

    async def main() -> _Recorder:
        peer = recorder or _Recorder()
        send_stream, receive_stream = anyio.create_memory_object_stream[StreamItem](1)
        response = EventStreamResponse(
            receive_stream,
            heartbeat_seconds=heartbeat,
            send_timeout_seconds=send_timeout,
            on_close=peer.on_close,
        )
        with anyio.fail_after(_DEADLINE):
            async with anyio.create_task_group() as group:
                group.start_soon(response, _SCOPE, peer.receive, peer.send)
                await drive(send_stream, peer)
        return peer

    return anyio.run(main)


def test_changes_are_framed_in_order_and_the_close_ends_cleanly() -> None:
    async def drive(items: MemoryObjectSendStream[StreamItem], _: _Recorder) -> None:
        async with items:
            await items.send(_CHANGE)

    peer = _run(drive)

    assert peer.sent[0]["status"] == 200
    assert (b"content-type", b"text/event-stream") in peer.sent[0]["headers"]
    assert peer.bodies == [change_frame(_CHANGE), b""]
    assert peer.sent[-1]["more_body"] is False
    assert peer.closes == 1


def test_an_idle_stream_sends_a_keepalive_each_heartbeat() -> None:
    async def drive(items: MemoryObjectSendStream[StreamItem], _: _Recorder) -> None:
        await anyio.sleep(0.18)
        await items.aclose()

    peer = _run(drive, heartbeat=0.05)

    keepalives = [b for b in peer.bodies if b == KEEPALIVE_FRAME]
    assert 2 <= len(keepalives) <= 4
    assert peer.closes == 1


def test_an_error_item_is_sent_once_and_closes_the_response() -> None:
    error = StreamError(ApiErrorCode.STORE_UNREADABLE, "gone")

    async def drive(items: MemoryObjectSendStream[StreamItem], _: _Recorder) -> None:
        await items.send(error)

    peer = _run(drive)

    assert peer.bodies == [error_frame(error), b""]
    assert peer.closes == 1


def test_a_send_that_never_returns_closes_after_the_send_timeout() -> None:
    class _Stalled(_Recorder):
        async def send(self, message: Message) -> None:
            if message["type"] == "http.response.body":
                await anyio.sleep_forever()
            await super().send(message)

    async def drive(items: MemoryObjectSendStream[StreamItem], _: _Recorder) -> None:
        await items.send(_CHANGE)

    started = time.monotonic()
    peer = _run(drive, send_timeout=0.1, recorder=_Stalled())
    elapsed = time.monotonic() - started

    assert peer.closes == 1
    assert 0.1 <= elapsed < 1.0
    assert peer.bodies == []


def test_a_client_disconnect_ends_the_stream() -> None:
    async def drive(items: MemoryObjectSendStream[StreamItem], peer: _Recorder) -> None:
        await items.send(_CHANGE)
        peer.disconnect.set()

    peer = _run(drive)

    assert peer.closes == 1
    assert peer.sent[-1]["type"] == "http.response.body"


@pytest.mark.parametrize("reason", ["error", "end", "disconnect", "stall"])
def test_on_close_runs_exactly_once_on_every_exit(reason: str) -> None:
    class _MaybeStalled(_Recorder):
        async def send(self, message: Message) -> None:
            if reason == "stall" and message["type"] == "http.response.body":
                await anyio.sleep_forever()
            await super().send(message)

    async def drive(items: MemoryObjectSendStream[StreamItem], peer: _Recorder) -> None:
        match reason:
            case "error":
                await items.send(StreamError(ApiErrorCode.STORE_UNREADABLE, "x"))
            case "end":
                await items.aclose()
            case "disconnect":
                peer.disconnect.set()
            case _:
                await items.send(_CHANGE)

    peer = _run(drive, send_timeout=0.1, recorder=_MaybeStalled())

    assert peer.closes == 1


def test_the_receive_side_is_closed_after_the_response_ends() -> None:
    """A follow thread blocked handing off a change must wake at once."""
    outcome: list[str] = []

    async def drive(items: MemoryObjectSendStream[StreamItem], peer: _Recorder) -> None:
        peer.disconnect.set()
        await anyio.sleep(0.05)
        try:
            await items.send(_CHANGE)
        except anyio.BrokenResourceError:
            outcome.append("broken")

    _run(drive)

    assert outcome == ["broken"]


def test_frames_are_valid_json_data() -> None:
    data = change_frame(_CHANGE).decode().split("data: ", 1)[1].strip()

    assert json.loads(data)["seq"] == 42
