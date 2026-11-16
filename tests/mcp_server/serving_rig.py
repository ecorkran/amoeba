"""Serve a ``Server`` through ``serve_pinned`` to an SDK client over memory streams
(slice 241): the in-process rig for the resource and serving tests."""

from __future__ import annotations

import warnings
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import anyio
from mcp import ClientSession
from mcp.client.session import IncomingMessage
from mcp.server import Server
from mcp.server.connection import Connection
from mcp.shared.exceptions import MCPDeprecationWarning
from mcp.shared.memory import create_client_server_memory_streams
from mcp_types import Implementation

from amoeba.mcp.inbox_resource import initialization_options
from amoeba.mcp.pinned_loop import Background, serve_pinned
from amoeba.mcp.presence import PresenceDeps, PresenceState
from amoeba.mcp.presence_task import run_presence


@dataclass
class Received:
    """What the client received besides responses."""

    messages: list[IncomingMessage] = field(default_factory=lambda: [])

    async def __call__(self, message: IncomingMessage) -> None:
        self.messages.append(message)

    def methods(self) -> list[str]:
        return [
            getattr(message, "method", type(message).__name__)
            for message in self.messages
        ]


def presence_background(state: PresenceState, deps: PresenceDeps) -> Background:
    """``run_presence`` for ``state`` and ``deps``, as ``serve_pinned`` starts it."""

    async def background(connection: Connection) -> None:
        await run_presence(connection, state, deps)

    return background


@asynccontextmanager
async def serving(
    server: Server[Any],
    background: Background,
    received: Received | None = None,
    client_name: str = "claude-code",
) -> AsyncGenerator[ClientSession]:
    """An initialized client session against ``server``; closing it ends the server."""
    async with create_client_server_memory_streams() as (
        client_streams,
        server_streams,
    ):
        async with anyio.create_task_group() as group:
            group.start_soon(_serve, server, server_streams, background)
            async with ClientSession(
                *client_streams,
                message_handler=received,
                client_info=Implementation(name=client_name, version="0"),
            ) as session:
                await session.initialize()
                yield session
            group.cancel_scope.cancel()


async def _serve(
    server: Server[Any], streams: tuple[Any, Any], background: Background
) -> None:
    await serve_pinned(
        server,
        streams,
        initialization_options(server),
        background,
        lifespan_state={},
    )


async def subscribe(session: ClientSession, uri: str) -> None:
    """``resources/subscribe``. The SDK marks it deprecated because the 2026-07-28 era
    dropped it; this server serves only the handshake era, where it is current."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MCPDeprecationWarning)
        await session.subscribe_resource(uri)  # pyright: ignore[reportDeprecated]


async def unsubscribe(session: ClientSession, uri: str) -> None:
    """``resources/unsubscribe``; see ``subscribe``."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MCPDeprecationWarning)
        await session.unsubscribe_resource(uri)  # pyright: ignore[reportDeprecated]
