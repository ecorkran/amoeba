"""The feed as Server-Sent Events (LLD D6).

:class:`EventStreamResponse` frames items from a 1-slot memory object stream.
Each send runs under a timeout, so a client that stops reading cannot hold the
stream forever. A disconnect is noticed on ``receive()``: uvicorn advertises
ASGI spec 2.3 and, measured 20261018 with 0.54, returns ``http.disconnect`` at
once while sends after it silently succeed. Heartbeats keep an idle connection
open through intermediaries.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import anyio
import anyio.from_thread
import anyio.lowlevel
from anyio.lowlevel import EventLoopToken
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from starlette.types import Message, Receive, Scope, Send

from amoeba.feed import FeedSettings, follow
from amoeba.feed.wire import change_record
from amoeba.serve.errors import (
    CODE_BY_EXCEPTION,
    ApiErrorCode,
    code_for_exception,
    error_body,
)
from amoeba.store import Change

#: The SSE comment an idle stream sends every heartbeat interval.
KEEPALIVE_FRAME: Final = b": keepalive\n\n"

#: The SSE event name of a change, and of the one error before a stream closes.
CHANGE_EVENT: Final = "change"
ERROR_EVENT: Final = "error"

_START: Final[Message] = {
    "type": "http.response.start",
    "status": 200,
    "headers": [
        (b"content-type", b"text/event-stream"),
        (b"cache-control", b"no-cache"),
    ],
}
_END: Final[Message] = {"type": "http.response.body", "body": b"", "more_body": False}
_DISCONNECT: Final = "http.disconnect"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StreamError:
    """A failure after the 200: sent as one ``event: error`` frame, then close."""

    code: ApiErrorCode
    detail: str


type StreamItem = Change | StreamError


def change_frame(change: Change) -> bytes:
    """``id`` is the ``seq``; ``data`` is the same object ``amoeba feed`` prints."""
    data = json.dumps(change_record(change))
    return f"id: {change.seq}\nevent: {CHANGE_EVENT}\ndata: {data}\n\n".encode()


def error_frame(error: StreamError) -> bytes:
    data = json.dumps(error_body(error.code, error.detail))
    return f"event: {ERROR_EVENT}\ndata: {data}\n\n".encode()


def _body(frame: bytes) -> Message:
    return {"type": "http.response.body", "body": frame, "more_body": True}


class EventStreamResponse:
    """An ASGI response streaming items until a close, an error, or a stalled peer.

    ``on_close`` runs exactly once, on every exit: it is how the caller stops
    the follow thread and releases the stream slot.
    """

    def __init__(
        self,
        items: MemoryObjectReceiveStream[StreamItem],
        *,
        heartbeat_seconds: float,
        send_timeout_seconds: float,
        on_close: Callable[[], None],
    ) -> None:
        self._items = items
        self._heartbeat = heartbeat_seconds
        self._send_timeout = send_timeout_seconds
        self._on_close = on_close

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            async with anyio.create_task_group() as group:
                group.start_soon(_cancel_on_disconnect, receive, group.cancel_scope)
                await self._stream(send)
                group.cancel_scope.cancel()
        finally:
            self._items.close()
            self._on_close()

    async def _stream(self, send: Send) -> None:
        """Send frames until done. Every exit path returns; nothing escapes."""
        try:
            await self._send(send, _START)
            while True:
                frame, last = await self._next_frame()
                if frame:
                    await self._send(send, _body(frame))
                if last:
                    await self._send(send, _END)
                    return
        except (TimeoutError, OSError):
            # Specific: a peer that stopped reading (the send timed out) or a
            # broken connection. The stream ends; the finally releases the slot.
            return

    async def _next_frame(self) -> tuple[bytes, bool]:
        """The next frame, and whether the stream ends after it."""
        with anyio.move_on_after(self._heartbeat):
            try:
                item = await self._items.receive()
            except anyio.EndOfStream:
                # Specific: the follow thread finished and closed its side.
                return b"", True
            if isinstance(item, StreamError):
                return error_frame(item), True
            return change_frame(item), False
        return KEEPALIVE_FRAME, False

    async def _send(self, send: Send, message: Message) -> None:
        with anyio.fail_after(self._send_timeout):
            await send(message)


async def _cancel_on_disconnect(receive: Receive, scope: anyio.CancelScope) -> None:
    """End the stream as soon as the client goes."""
    while (await receive())["type"] != _DISCONNECT:
        pass
    scope.cancel()


#: Every follow thread's name starts with this, so tests can find leaks.
FOLLOW_THREAD_PREFIX: Final = "amoeba-follow-"

#: Raised by a hand-off once the response has ended, or the loop has gone.
_HAND_OFF_ENDED: Final = (
    anyio.ClosedResourceError,
    anyio.BrokenResourceError,
    anyio.RunFinishedError,
)


@dataclass(frozen=True)
class FollowRequest:
    """What one stream follows, and from where."""

    store_dir: Path
    project_id: str
    after: int
    feed: FeedSettings


def start_follow_thread(
    request: FollowRequest,
    items: MemoryObjectSendStream[StreamItem],
    stop: threading.Event,
) -> threading.Thread:
    """Start the dedicated thread bridging ``follow()`` to this event loop.

    Call it on the event loop: it captures the loop's token. Each change is
    handed off through the 1-slot ``items`` stream and the thread waits until
    the loop takes it, so a slow client only slows the read of the durable log.
    """
    token = anyio.lowlevel.current_token()
    thread = threading.Thread(
        target=_follow_into,
        args=(request, items, stop, token),
        name=f"{FOLLOW_THREAD_PREFIX}{request.project_id}",
        daemon=True,
    )
    thread.start()
    return thread


def _follow_into(
    request: FollowRequest,
    items: MemoryObjectSendStream[StreamItem],
    stop: threading.Event,
    token: EventLoopToken,
) -> None:
    """The thread body. Every exit closes the send side, so the response ends."""
    changes = follow(
        request.store_dir,
        request.project_id,
        after=request.after,
        settings=request.feed,
        stop=stop.is_set,
    )
    try:
        with closing(changes):
            for change in changes:
                anyio.from_thread.run(items.send, change, token=token)
    except _HAND_OFF_ENDED:
        # Specific: the response closed its side (disconnect, timeout, shutdown)
        # or the loop is gone. This is how a thread blocked in a hand-off stops.
        pass
    except tuple(CODE_BY_EXCEPTION) as error:
        # Specific: the store vanished or changed schema after the 200. The
        # client gets one error frame; follow() has already closed its store.
        _hand_off_error(
            items, StreamError(code_for_exception(error), str(error)), token
        )
    except Exception:
        # The thread's boundary handler: nothing above this catches for it.
        logger.exception("follow thread for %s failed", request.project_id)
        _hand_off_error(
            items, StreamError(ApiErrorCode.INTERNAL_ERROR, "internal error"), token
        )
    finally:
        _close(items, token)


def _hand_off_error(
    items: MemoryObjectSendStream[StreamItem], error: StreamError, token: EventLoopToken
) -> None:
    try:
        anyio.from_thread.run(items.send, error, token=token)
    except _HAND_OFF_ENDED:
        # Specific: the client is already gone; there is no one to tell.
        pass


def _close(items: MemoryObjectSendStream[StreamItem], token: EventLoopToken) -> None:
    try:
        anyio.from_thread.run_sync(items.close, token=token)
    except anyio.RunFinishedError:
        # Specific: the loop is gone, so no one can race the close.
        items.close()
