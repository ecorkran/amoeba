"""``amoeba-mcp``: the CLI's operations as MCP tools over stdio (slice 226, D1, D7).

A low-level server, so the published schema is each operation's own request model
and the raw arguments reach the operation unvalidated (the operations validate their
own input, so both doors give the same ``rejected`` result). Nothing here holds
operation logic: ``call_tool`` looks the tool up, runs it through ``in_process`` or
``detached``, and maps the outcome to a result or an ``isError`` text. Nothing prints
to stdout; logging goes to stderr.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping
from typing import Any, Final

import anyio
import anyio.to_thread
import mcp_types as types
from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server

from amoeba import wiring
from amoeba.mcp.detached import (
    AmoebaScriptMissing,
    HandlePauseNotStarted,
    resolve_amoeba_script,
    start_handle_pause,
)
from amoeba.mcp.in_process import (
    MCP_CALL_DEADLINE_SECONDS,
    CallTimedOut,
    run_in_process,
)
from amoeba.mcp.tools import (
    TOOLS,
    RequestError,
    RunMode,
    ToolSpec,
    input_schema,
    prepare_arguments,
)

logger = logging.getLogger(__name__)

SERVER_NAME: Final = "amoeba"
#: Exit status of ``amoeba-mcp`` when it refuses to start.
EXIT_START_FAILED: Final = 1
INSTRUCTIONS: Final = (
    "Amoeba keeps unattended Squadron pipeline runs moving. When a run pauses on a "
    "question, Amoeba answers it from the project's own rules, plan and the PM's "
    "earlier answers when those settle it, and records every answer and every "
    "decline. Questions they do not settle wait for the PM. Use these tools when the "
    "PM asks what is waiting, wants to answer a waiting question, wants to know what "
    "was decided while away, or wants a repo registered. Several repos form a "
    "program, and Amoeba answers across it.\n\n"
    "These tools are the `amoeba` command's operations, with the same inputs and "
    "results.\n"
    "- What needs the PM, or what is registered: `list` (or `status`). Its listing "
    "gives the `run_id` and `directory` for `handle_pause` and the question key for "
    "`answer`.\n"
    "- The PM gives a decision on a waiting question: `answer`. It carries only a "
    "decision the PM actually gave, passed on as given, never one you composed, "
    "because it becomes precedent for later questions. `retract` stops an answer "
    "being precedent; `dismiss` closes a question that has no answer to deliver.\n"
    "- What was decided while the PM was away: `decisions`, then `mark_read` with "
    "its `read_through`.\n"
    "- Register or unregister a repo: `add` and `rm`. `add` needs only the "
    "directory; the repo's CLAUDE.md and AGENTS.md are read as its rules.\n"
    "- Repos that depend on one another: `changes` before designing a slice, to "
    "see what the repos this one depends on reported since a time you give it; "
    "`report_release` after a merge or release that other repos use, to tell them "
    "what changed (it also corrects or withdraws a report).\n"
    "- `handle_pause` is normally started by Squadron's pause hook, not by you. It "
    "starts the work and returns a receipt; its result lands in the receipt's "
    "stdout log."
)
#: Failures reported as ``<ExceptionName>: <message>``: the operational errors, an
#: ``answer`` refused for a config the deadline cannot cover, and the two ways a
#: detached start fails.
_REPORTED_ERRORS: Final = (
    *wiring.OPERATIONAL_ERRORS,
    wiring.DeadlineError,
    AmoebaScriptMissing,
    HandlePauseNotStarted,
)


def _ok(document: dict[str, object]) -> types.CallToolResult:
    """A result: the JSON as ``structuredContent`` and as one text block."""
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(document))],
        structured_content=document,
        is_error=False,
    )


def _error(text: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)], is_error=True
    )


def _spec_named(name: str) -> ToolSpec | None:
    return next((tool for tool in TOOLS if tool.name.value == name), None)


async def _run(
    spec: ToolSpec, arguments: Mapping[str, object] | None
) -> dict[str, object]:
    """Run the tool and return its JSON result; the errors propagate to the caller."""
    if spec.mode is RunMode.DETACHED:
        # ``HandlePauseCall`` is the one validator of the detached request, the
        # directory included.
        return (await start_handle_pause(arguments)).model_dump(mode="json")
    document, directory = prepare_arguments(spec, arguments)
    return await run_in_process(spec, document, directory)


async def call_tool(
    name: str, arguments: Mapping[str, object] | None
) -> types.CallToolResult:
    """Run the tool ``name``; every outcome is a result, never an exception.

    This is the process boundary: the expected failures become ``isError`` texts
    (D7), and anything else is logged and reported as an internal error while the
    server keeps serving.
    """
    spec = _spec_named(name)
    if spec is None:
        return _error(f"unknown tool: {name}")
    try:
        document = await _run(spec, arguments)
        # Serialized in a thread: a long ``decisions`` listing is not loop-sized work.
        return await anyio.to_thread.run_sync(_ok, document)
    except RequestError as error:
        return _error(f"RequestError: {error}")
    except CallTimedOut as error:
        return _error(f"TimedOut: {error}")
    except _REPORTED_ERRORS as error:
        return _error(f"{type(error).__name__}: {error}")
    except Exception as error:
        logger.exception("tool %s failed unexpectedly", name)
        return _error(f"internal error: {error}")


async def _on_call_tool(
    ctx: ServerRequestContext[Any], params: types.CallToolRequestParams
) -> types.CallToolResult:
    return await call_tool(params.name, params.arguments)


def build_server() -> Server[Any]:
    """The MCP server: one tool per ``TOOLS`` row, no input validation by the SDK.

    The published tools, with their schemas, are built once here, not per request.
    """
    published = types.ListToolsResult(
        tools=[
            types.Tool(
                name=spec.name.value,
                description=spec.description,
                input_schema=input_schema(spec),
            )
            for spec in TOOLS
        ]
    )

    async def on_list_tools(
        ctx: ServerRequestContext[Any], params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        return published

    return Server(
        SERVER_NAME,
        instructions=INSTRUCTIONS,
        on_list_tools=on_list_tools,
        on_call_tool=_on_call_tool,
    )


async def _serve() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def serve() -> None:
    """Serve over stdio until the client closes its end."""
    anyio.run(_serve)


def _refuse_to_start(error: Exception) -> None:
    sys.stderr.write(f"error: {type(error).__name__}: {error}\n")
    raise SystemExit(EXIT_START_FAILED)


def main() -> None:
    """Check the install and the config, move legacy state, then serve.

    Each failure to start is one stderr line, which the client shows, and a non-zero
    exit: a missing ``amoeba`` script, a failed state move (the next session start
    tries again), or a config whose ``resume_wait_seconds`` is too large for the call
    deadline.
    """
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        resolve_amoeba_script()
        wiring.prepare_home()
        wiring.check_deadline(wiring.load_config(), MCP_CALL_DEADLINE_SECONDS)
    except (AmoebaScriptMissing, wiring.DeadlineError, *wiring.OPERATIONAL_ERRORS) as e:
        _refuse_to_start(e)
    serve()
