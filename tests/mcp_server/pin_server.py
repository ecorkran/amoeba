"""A tiny MCP server for ``test_protocol_pin.py`` (slice 241, D1), run as a script.

``pin_server.py pinned <marker>`` serves through ``serve_pinned`` with a background
task that writes ``started`` to ``<marker>`` and, when cancelled, ``cancelled``.
``pin_server.py dual`` serves the same ``Server`` through ``Server.run``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

import anyio
from mcp.server import Server
from mcp.server.connection import Connection
from mcp.server.stdio import stdio_server

from amoeba.mcp.pinned_loop import Background, serve_pinned

PINNED: Final = "pinned"
DUAL: Final = "dual"
STARTED: Final = "started"
CANCELLED: Final = "cancelled"


def _marking_background(marker: Path) -> Background:
    async def background(connection: Connection) -> None:
        # Started with the live connection, which presence sends notifications on.
        assert isinstance(connection, Connection)
        await anyio.Path(marker).write_text(STARTED, encoding="utf-8")
        try:
            await anyio.sleep_forever()
        finally:
            # Shielded: the write runs inside the cancellation it records.
            with anyio.CancelScope(shield=True):
                await anyio.Path(marker).write_text(CANCELLED, encoding="utf-8")

    return background


async def _serve(mode: str, marker: Path | None) -> None:
    server: Server[object] = Server("pin-probe")
    async with stdio_server() as streams:
        if mode == DUAL:
            await server.run(*streams, server.create_initialization_options())
            return
        assert marker is not None
        async with server.lifespan(server) as lifespan_state:
            await serve_pinned(
                server,
                streams,
                server.create_initialization_options(),
                _marking_background(marker),
                lifespan_state=lifespan_state,
            )


if __name__ == "__main__":
    MODE = sys.argv[1]
    anyio.run(_serve, MODE, Path(sys.argv[2]) if MODE == PINNED else None)
