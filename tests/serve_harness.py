"""Shared helpers for the server tests. Nothing here binds off loopback."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Generator, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import uvicorn
from starlette.testclient import TestClient
from starlette.types import ASGIApp, Message, Scope


@dataclass(frozen=True)
class TlsFiles:
    """A self-signed localhost certificate, its key, and a key that does not match."""

    certfile: Path
    keyfile: Path
    other_keyfile: Path


#: A TEST VALUE ONLY, never a real credential: 48 hex characters, as
#: ``openssl rand -hex 24`` would produce.
TEST_TOKEN = "0123456789abcdef" * 3

#: Every request the test client sends goes to this loopback origin.
BASE_URL = "http://127.0.0.1"

#: ``make_client(token=None, settings=None, *, raise_server_exceptions=True)``.
type ClientFactory = Callable[..., TestClient]


@dataclass
class AsgiExchange:
    """One request made by calling the app as an ASGI callable, and what it did."""

    status: int = 0
    body: bytes = b""
    receive_calls: int = 0
    bytes_handed_out: int = 0
    chunk_sizes: list[int] = field(default_factory=list[int])


async def call_asgi(
    app: ASGIApp,
    method: str,
    path: str,
    *,
    content_type: str = "application/json",
    chunks: Sequence[bytes] = (),
) -> AsgiExchange:
    """Call ``app`` with an unnormalized ``path``, handing the body out chunk by chunk.

    A real client normalizes ``.`` and ``..`` segments away; this is what the
    app receives from a raw request. The scope passes the request guard: host
    ``127.0.0.1``, no ``Origin``, and (for the caller to arrange) no token.
    """
    exchange = AsgiExchange()
    pending = list(chunks)

    async def receive() -> Message:
        exchange.receive_calls += 1
        if not pending:
            return {"type": "http.request", "body": b"", "more_body": False}
        chunk = pending.pop(0)
        exchange.bytes_handed_out += len(chunk)
        exchange.chunk_sizes.append(len(chunk))
        return {"type": "http.request", "body": chunk, "more_body": bool(pending)}

    async def send(message: Message) -> None:
        if message["type"] == "http.response.start":
            exchange.status = int(message["status"])
        elif message["type"] == "http.response.body":
            exchange.body += bytes(message.get("body", b""))

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"127.0.0.1"), (b"content-type", content_type.encode())],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8765),
    }
    await app(scope, receive, send)
    return exchange


#: How long the harness waits for a server to start or stop. Never reached.
SERVER_DEADLINE_SECONDS = 10.0

#: Thread name prefix for harness servers, so leak checks can find them.
SERVER_THREAD_PREFIX = "serve-harness"


@contextmanager
def running_server(app: ASGIApp, *, grace_seconds: int = 1) -> Generator[str]:
    """A real uvicorn on an ephemeral loopback port, in a background thread.

    Yields the base URL. Stops with ``should_exit`` and joins the thread, so no
    thread outlives the block. ``grace_seconds`` bounds the wait for open
    connections (an SSE stream never ends on its own).
    """
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=0,
        log_config=None,
        timeout_graceful_shutdown=grace_seconds,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(
        target=server.run, name=f"{SERVER_THREAD_PREFIX}-{id(server)}", daemon=True
    )
    thread.start()
    deadline = time.monotonic() + SERVER_DEADLINE_SECONDS
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("the harness server did not start")
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(SERVER_DEADLINE_SECONDS)
        if thread.is_alive():
            raise RuntimeError("the harness server did not stop")


@dataclass(frozen=True)
class SseEvent:
    """One SSE frame: a comment, or an event with its fields."""

    id: str | None = None
    event: str | None = None
    data: str | None = None
    comment: str | None = None


def sse_events(lines: Iterator[str]) -> Iterator[SseEvent]:
    """Frames from an SSE line stream, split on blank lines.

    Pass ``response.iter_lines()`` from a client whose read timeout bounds each
    wait; a frame that never comes raises the client's timeout, never hangs.
    """
    fields: dict[str, str] = {}
    for line in lines:
        if line == "":
            if fields:
                yield SseEvent(**fields)
            fields = {}
        elif line.startswith(":"):
            fields["comment"] = line[1:].strip()
        else:
            name, _, value = line.partition(":")
            fields[name] = value.removeprefix(" ")
