"""A stdio MCP server whose one tool answers after 220 seconds (slice 263, D15 step 1).

It is built on ``serve_pinned`` as ``pin_server.py`` is, with no hub and no Amoeba
store. ``tests/live/channels/test_long_call_live.py`` registers it with a real Claude
Code session to see what the session does with a tool call that runs past two minutes.
"""

from __future__ import annotations

from typing import Any, Final

import anyio
import mcp_types as types
from mcp.server import Server, ServerRequestContext
from mcp.server.connection import Connection
from mcp.server.stdio import stdio_server

from amoeba.mcp.pinned_loop import serve_pinned

SERVER_NAME: Final = "longcall"
TOOL_NAME: Final = "wait_a_while"
#: How long the tool waits: past the two minutes after which Claude Code may move a
#: call to the background, under the 300-second deadline D9 sets.
WAIT_SECONDS: Final = 220
MARKER: Final = "LONG-CALL-MARKER-7f3a"


async def _no_background(connection: Connection) -> None:
    del connection
    await anyio.sleep_forever()


def build_server() -> Server[Any]:
    published = types.ListToolsResult(
        tools=[
            types.Tool(
                name=TOOL_NAME,
                description=(
                    f"Waits {WAIT_SECONDS} seconds, then returns a marker string."
                ),
                input_schema={"type": "object", "properties": {}},
            )
        ]
    )

    async def on_list_tools(
        ctx: ServerRequestContext[Any], params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        return published

    async def on_call_tool(
        ctx: ServerRequestContext[Any], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        await anyio.sleep(WAIT_SECONDS)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=MARKER)], is_error=False
        )

    return Server(SERVER_NAME, on_list_tools=on_list_tools, on_call_tool=on_call_tool)


async def _serve() -> None:
    server = build_server()
    async with stdio_server() as streams, server.lifespan(server) as lifespan_state:
        await serve_pinned(
            server,
            streams,
            server.create_initialization_options(),
            _no_background,
            lifespan_state=lifespan_state,
        )


if __name__ == "__main__":
    anyio.run(_serve)
