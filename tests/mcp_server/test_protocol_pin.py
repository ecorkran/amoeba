"""The protocol pin, over real stdio with a raw JSON-RPC driver (slice 241, D1).

Claude Code opens every stdio server with a ``server/discover`` probe for 2026-07-28
and registers no channel on a server that answers it. ``serve_pinned`` must answer
the probe ``Method not found`` and then serve ``initialize`` at a handshake-era
version. ``Server.run`` does the opposite: it answers the probe with
``supportedVersions`` and then refuses ``initialize`` (-32022). Both are asserted, so
an SDK change to either loop fails here rather than in a session. No SDK client is
used: the client's own era choice must not stand between the test and the wire.
"""

from __future__ import annotations

import json
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Final

import pytest
from mcp_types.version import HANDSHAKE_PROTOCOL_VERSIONS, MODERN_PROTOCOL_VERSIONS
from process_containment import contained_popen

from mcp_server.pin_server import CANCELLED, DUAL, PINNED, STARTED

PIN_SERVER: Final = Path(__file__).with_name("pin_server.py")
REPLY_TIMEOUT_SECONDS: Final = 15
EXIT_TIMEOUT_SECONDS: Final = 15
METHOD_NOT_FOUND: Final = -32601
#: The SDK's code for "this connection serves the modern era; no handshake".
HANDSHAKE_REFUSED: Final = -32022
MODERN_VERSION: Final = MODERN_PROTOCOL_VERSIONS[-1]
HANDSHAKE_VERSION: Final = HANDSHAKE_PROTOCOL_VERSIONS[-1]
CLIENT_INFO: Final = {"name": "raw-pin-driver", "version": "0"}
#: The probe as Claude Code sends it (observed 20261116): the era in ``_meta``.
DISCOVER: Final = {
    "jsonrpc": "2.0",
    "id": "probe-1",
    "method": "server/discover",
    "params": {
        "_meta": {
            "io.modelcontextprotocol/protocolVersion": MODERN_VERSION,
            "io.modelcontextprotocol/clientInfo": CLIENT_INFO,
            "io.modelcontextprotocol/clientCapabilities": {},
        }
    },
}
INITIALIZE: Final = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": HANDSHAKE_VERSION,
        "capabilities": {},
        "clientInfo": CLIENT_INFO,
    },
}


class RawServer:
    """The pin server as a child, spoken to one JSON line at a time."""

    def __init__(self, *args: str) -> None:
        self.process: subprocess.Popen[bytes] = contained_popen(
            [sys.executable, str(PIN_SERVER), *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def request(self, message: dict[str, Any]) -> dict[str, Any]:
        stdin, stdout = self.process.stdin, self.process.stdout
        assert stdin is not None and stdout is not None
        stdin.write(json.dumps(message).encode("utf-8") + b"\n")
        stdin.flush()
        ready, _, _ = select.select([stdout], [], [], REPLY_TIMEOUT_SECONDS)
        assert ready, f"no reply to {message['method']} in {REPLY_TIMEOUT_SECONDS}s"
        reply: dict[str, Any] = json.loads(stdout.readline())
        assert reply["id"] == message["id"]
        return reply

    def close_stdin_and_wait(self) -> int:
        assert self.process.stdin is not None
        self.process.stdin.close()
        return self.process.wait(timeout=EXIT_TIMEOUT_SECONDS)


@pytest.fixture
def marker(tmp_path: Path) -> Path:
    return tmp_path / "background.marker"


def test_the_pinned_loop_refuses_the_probe_and_serves_the_handshake(
    marker: Path,
) -> None:
    server = RawServer(PINNED, str(marker))

    probe = server.request(DISCOVER)
    initialized = server.request(INITIALIZE)
    server.close_stdin_and_wait()

    assert probe["error"]["code"] == METHOD_NOT_FOUND
    assert initialized["result"]["protocolVersion"] in HANDSHAKE_PROTOCOL_VERSIONS


def test_server_run_answers_the_probe_and_then_refuses_the_handshake() -> None:
    server = RawServer(DUAL)

    probe = server.request(DISCOVER)
    initialized = server.request(INITIALIZE)
    server.close_stdin_and_wait()

    assert MODERN_VERSION in probe["result"]["supportedVersions"]
    assert initialized["error"]["code"] == HANDSHAKE_REFUSED


def test_the_background_gets_the_connection_and_is_cancelled_when_the_client_leaves(
    marker: Path,
) -> None:
    server = RawServer(PINNED, str(marker))
    server.request(INITIALIZE)
    deadline = time.monotonic() + REPLY_TIMEOUT_SECONDS
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert marker.read_text(encoding="utf-8") == STARTED

    exit_code = server.close_stdin_and_wait()

    assert exit_code == 0
    assert marker.read_text(encoding="utf-8") == CANCELLED
