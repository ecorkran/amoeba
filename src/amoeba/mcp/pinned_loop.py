"""A handshake-only serve loop that runs a background task beside it (slice 241, D1).

``Server.run`` in mcp 2.3 serves two protocol eras and lets the client's first request
pick one. Claude Code opens with a ``server/discover`` probe for 2026-07-28 and does
not register a channel on a server that answers it; a handshake-only loop answers the
probe ``Method not found``, and the client falls back to ``initialize``. So the pin is
this loop choice, not a version constant.

``serve_pinned`` mirrors the SDK's ``serve_loop`` (``mcp/server/runner.py``), which
builds its ``Connection`` internally, and adds only what ``serve_loop`` cannot give: the
connection, handed to ``background`` so it can send notifications.
``tests/mcp_server/test_protocol_pin.py`` fails if either loop's behavior changes.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import anyio
from mcp.server import Server
from mcp.server.connection import Connection
from mcp.server.models import InitializationOptions
from mcp.server.runner import serve_connection
from mcp.shared.jsonrpc_dispatcher import JSONRPCDispatcher
from mcp.shared.transport_context import TransportContext

#: The task run beside the loop; it gets the connection and is cancelled at the end.
Background = Callable[[Connection], Coroutine[Any, Any, None]]


async def serve_pinned(
    server: Server[Any],
    streams: tuple[Any, Any],
    init_options: InitializationOptions,
    background: Background,
    *,
    lifespan_state: Any,
) -> None:
    """Serve ``server`` in handshake-only mode until the client closes its end.

    ``streams`` is the read and write pair a transport yields (``stdio_server``, or
    memory streams in tests); typed ``Any`` because the SDK defines their protocols
    only in a private module. ``background`` starts with the connection and is
    cancelled once ``serve_connection`` returns. ``lifespan_state`` is what the
    server's lifespan yielded, as ``Server.run`` passes it.
    """
    read_stream, write_stream = streams
    dispatcher: JSONRPCDispatcher[TransportContext] = JSONRPCDispatcher(
        read_stream,
        write_stream,
        # As serve_loop: ``initialize`` inline, so a client that pipelines it with
        # the next request sees the initialized state.
        inline_methods=frozenset({"initialize"}),
    )
    connection = Connection.for_loop(dispatcher)
    async with anyio.create_task_group() as group:
        group.start_soon(background, connection)
        await serve_connection(
            server,
            dispatcher,
            connection=connection,
            lifespan_state=lifespan_state,
            init_options=init_options,
        )
        group.cancel_scope.cancel()
