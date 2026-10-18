"""Shared helpers for the server tests. Nothing here binds off loopback."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

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
