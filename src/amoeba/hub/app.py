"""The hub's web app: one Starlette route, ``POST /call/{name}`` (slice 260, D14).

The handler refuses a body with no valid length, or one over ``MAX_CALL_BYTES``,
before reading it. Otherwise it reads the body and runs ``handle_call`` in a worker
thread through ``anyio``, so no store call runs on the event loop. Every reply carries
``Amoeba-Door-Version``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Final

import anyio.to_thread
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from amoeba.hub.call_refusals import CallReply, Refuser
from amoeba.hub.calls import CallRequest
from amoeba.wire.protocol import (
    CALL_PATH_PREFIX,
    HEADER_DOOR_VERSION,
    MAX_CALL_BYTES,
    RefusalCode,
)
from amoeba.wire.times import DOOR_VERSION

CONTENT_LENGTH: Final = "content-length"
JSON_TYPE: Final = "application/json"
#: Where the caller is unknown (a transport with no peer address).
UNKNOWN_PEER: Final = "unknown"

type CallHandler = Callable[[CallRequest], CallReply]


def _declared_length(request: Request) -> int | None:
    """The body length the caller declared, or ``None`` when missing or invalid."""
    value = request.headers.get(CONTENT_LENGTH)
    if value is None or not value.isascii() or not value.isdigit():
        return None
    return int(value)


def _peer(request: Request) -> str:
    client = request.client
    return UNKNOWN_PEER if client is None else f"{client.host}:{client.port}"


def _response(reply: CallReply, door_version: int) -> Response:
    return Response(
        reply.body,
        status_code=reply.status,
        media_type=JSON_TYPE,
        headers={HEADER_DOOR_VERSION: str(door_version)},
    )


def create_app(
    handle: CallHandler,
    clock: Callable[[], datetime],
    door_version: int = DOOR_VERSION,
) -> Starlette:
    """The app that hands each call to ``handle`` in a worker thread."""

    async def call(request: Request) -> Response:
        peer = _peer(request)
        length = _declared_length(request)
        if length is None or length > MAX_CALL_BYTES:
            return _response(
                Refuser(clock, peer).refuse(
                    RefusalCode.MALFORMED_CALL,
                    f"a call needs a Content-Length of at most {MAX_CALL_BYTES} bytes",
                ),
                door_version,
            )
        body = await request.body()
        name = request.path_params["name"]
        call_request = CallRequest(
            name=name, headers=dict(request.headers), body=body, peer=peer
        )
        reply = await anyio.to_thread.run_sync(handle, call_request)
        return _response(reply, door_version)

    return Starlette(
        routes=[Route(f"{CALL_PATH_PREFIX}{{name}}", call, methods=["POST"])]
    )
