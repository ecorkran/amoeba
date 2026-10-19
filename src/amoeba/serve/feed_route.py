"""``GET /v1/projects/{project_id}/feed``: cursor, stream slot, preflight, stream.

Joins the follow thread and :class:`EventStreamResponse` (``stream.py``). The
endpoint is a raw ASGI callable because the response is one: Starlette treats a
class endpoint as an ASGI app and still maps exceptions raised before the 200.
"""

from __future__ import annotations

import threading
from functools import partial
from pathlib import Path
from typing import Final

import anyio
import anyio.to_thread
from starlette.requests import Request
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from amoeba.serve.errors import ApiError, ApiErrorCode
from amoeba.serve.reads import existing_store_path, validated_project_id
from amoeba.serve.settings import ServeSettings
from amoeba.serve.stream import (
    EventStreamResponse,
    FollowRequest,
    StreamItem,
    start_follow_thread,
)
from amoeba.store import Store

#: The query parameter, and the reconnect header that wins over it.
AFTER_PARAMETER: Final = "after"
LAST_EVENT_ID_HEADER: Final = "last-event-id"


def parse_cursor(last_event_id: str | None, after: list[str]) -> int:
    """``Last-Event-ID`` if present, else ``?after=``, else 0.

    Raises:
        ApiError: ``invalid_cursor`` unless the one that applies is a single
            non-negative integer.
    """
    if len(after) > 1:
        raise ApiError(ApiErrorCode.INVALID_CURSOR, "after may be given once")
    value = last_event_id if last_event_id is not None else next(iter(after), "0")
    if not (value.isascii() and value.isdigit()):
        raise ApiError(
            ApiErrorCode.INVALID_CURSOR,
            f"a cursor must be a non-negative integer, got {value!r}",
        )
    return int(value)


def _preflight(store_dir: Path, project_id: str) -> None:
    """Blocking: refuse an unknown or unreadable store before any byte is sent."""
    with Store.open_read_only(existing_store_path(store_dir, project_id)):
        pass


class FeedEndpoint:
    """One SSE stream per request, bounded by the stream slots."""

    def __init__(
        self, settings: ServeSettings, store_dir: Path, slots: anyio.CapacityLimiter
    ) -> None:
        self._settings = settings
        self._store_dir = store_dir
        self._slots = slots

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive)
        project_id = validated_project_id(str(request.path_params["project_id"]))
        cursor = parse_cursor(
            request.headers.get(LAST_EVENT_ID_HEADER),
            request.query_params.getlist(AFTER_PARAMETER),
        )
        release = self._acquire_slot()
        try:
            await anyio.to_thread.run_sync(
                partial(_preflight, self._store_dir, project_id)
            )
        except BaseException:
            release()
            raise
        await self._stream(project_id, cursor, release)(scope, receive, send)

    def _acquire_slot(self) -> _Release:
        """Take a slot without waiting; return the one-shot release."""
        borrower = object()
        try:
            self._slots.acquire_on_behalf_of_nowait(borrower)
        except anyio.WouldBlock as error:
            raise ApiError(
                ApiErrorCode.STREAM_LIMIT_REACHED,
                f"all {self._settings.max_streams} streams are open",
            ) from error
        return _Release(self._slots, borrower)

    def _stream(
        self, project_id: str, cursor: int, release: _Release
    ) -> EventStreamResponse:
        send_items, receive_items = anyio.create_memory_object_stream[StreamItem](1)
        stop = threading.Event()

        def on_close() -> None:
            stop.set()
            release()

        follow = FollowRequest(self._store_dir, project_id, cursor, self._settings.feed)
        start_follow_thread(follow, send_items, stop)
        return EventStreamResponse(
            receive_items,
            heartbeat_seconds=self._settings.heartbeat_interval_seconds,
            send_timeout_seconds=self._settings.send_timeout_seconds,
            on_close=on_close,
        )


class _Release:
    """Releases one slot, once, however many exit paths call it."""

    def __init__(self, slots: anyio.CapacityLimiter, borrower: object) -> None:
        self._slots = slots
        self._borrower = borrower
        self._released = False

    def __call__(self) -> None:
        if not self._released:
            self._released = True
            self._slots.release_on_behalf_of(self._borrower)


def routes(settings: ServeSettings, store_dir: Path) -> list[Route]:
    """The feed route, with its own slot limiter."""
    slots = anyio.CapacityLimiter(settings.max_streams)
    endpoint = FeedEndpoint(settings, store_dir, slots)
    return [Route("/v1/projects/{project_id}/feed", endpoint, methods=["GET"])]
