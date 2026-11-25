"""``amoeba-mcp`` over real stdio in a repo of a joined client home (slice 263, D15).

``serve_mcp`` starts the installed server in a repo of a ``ClientHome`` of the
two-machine fixture, with that home's own stub ``cf`` and ``sq`` and its client file,
and connects the SDK's client to it. The run exposes the notifications the server sent
(its channel events, and the resource updates the SDK surfaces) and the server's
stderr, whose lines are how a test sees a tick, a presence line or a skipped tick.
Leaving the context closes the server's stdin, which ends it; its clean exit deletes
the session's row.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import anyio
import mcp_types as types
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.client.extension import NotificationBinding
from mcp_types.version import LATEST_HANDSHAKE_VERSION
from process_containment import contained_popen
from pydantic import BaseModel, ConfigDict

from amoeba.mcp.channel_event import CHANNEL_METHOD

if TYPE_CHECKING:
    from hub_fixture import FixtureHub

SERVER: Final = Path(sys.executable).with_name("amoeba-mcp")
SESSION_TIMEOUT_SECONDS: Final = 120.0
WAIT_SECONDS: Final = 30.0
POLL_STEP_SECONDS: Final = 0.05
#: The stderr line that says a session found its member (``mcp.tick``).
PRESENCE_MARKER: Final = "presence for "
#: The stderr line a channel event attempt leaves.
EVENT_MARKER: Final = "channel event attempted"


class ChannelParams(BaseModel):
    """The params of a channel notification as the client reads them."""

    model_config = ConfigDict(extra="allow")

    content: str = ""
    meta: dict[str, Any] = {}


@dataclass
class McpRun:
    """A server that has been through the handshake, and what it has sent so far."""

    session: ClientSession
    stderr_path: Path
    #: Channel events, in arrival order.
    channel_events: list[ChannelParams] = field(
        default_factory=lambda: list[ChannelParams]()
    )
    #: Every other server notification the SDK surfaced.
    notifications: list[Any] = field(default_factory=lambda: list[Any]())

    def stderr(self) -> str:
        return self.stderr_path.read_text(encoding="utf-8")

    def stderr_lines(self, marker: str) -> list[str]:
        return [line for line in self.stderr().splitlines() if marker in line]

    async def wait_for(
        self, what: str, found: Any, seconds: float = WAIT_SECONDS
    ) -> None:
        """Wait until ``found()`` is true; the failure names ``what`` and the stderr."""
        with anyio.move_on_after(seconds) as scope:
            # Polls the stderr file a child process writes: no event to wait on.
            while not found():  # noqa: ASYNC110
                await anyio.sleep(POLL_STEP_SECONDS)
        assert not scope.cancelled_caught, (
            f"waited {seconds}s for {what}\nstderr:\n{self.stderr()}"
        )

    async def wait_for_presence(self, machine: str) -> str:
        """The presence line naming ``machine``, once the session has its member."""
        await self.wait_for(
            f"the presence line for {machine}",
            lambda: any(
                f"machine {machine}" in line
                for line in self.stderr_lines(PRESENCE_MARKER)
            ),
        )
        (line,) = [
            line
            for line in self.stderr_lines(PRESENCE_MARKER)
            if f"machine {machine}" in line
        ][:1]
        return line


@asynccontextmanager
async def serve_mcp(
    environment: Mapping[str, str], directory: Path, stderr_path: Path
) -> AsyncGenerator[McpRun]:
    """``amoeba-mcp`` started in ``directory`` with ``environment``, connected.

    ``environment`` is a client home's (``FixtureHub.env_for``); the server's stderr is
    written to ``stderr_path``.
    """
    parameters = StdioServerParameters(
        command=str(SERVER), args=[], env=dict(environment), cwd=directory
    )
    holder: list[McpRun] = []

    async def on_message(message: Any) -> None:
        if isinstance(message, types.ServerNotification) or isinstance(
            message, BaseException
        ):
            holder[0].notifications.append(message)

    async def on_channel(params: ChannelParams) -> None:
        holder[0].channel_events.append(params)

    binding = NotificationBinding(
        method=CHANNEL_METHOD, params_type=ChannelParams, handler=on_channel
    )
    with stderr_path.open("w", encoding="utf-8") as errlog:
        with anyio.fail_after(SESSION_TIMEOUT_SECONDS):
            async with stdio_client(parameters, errlog=errlog) as (read, write):
                async with ClientSession(
                    read,
                    write,
                    message_handler=on_message,
                    notification_bindings=[binding],
                ) as session:
                    holder.append(McpRun(session, stderr_path))
                    await session.initialize()
                    yield holder[0]


def set_hub_timings(hub: FixtureHub, **values: float) -> None:
    """Rewrite the named timing keys in the hub's ``config.yaml``. The hub reads the
    file on every call, so the next call serves the new values."""
    path = hub.home / "config.yaml"
    text = path.read_text(encoding="utf-8")
    for key, value in values.items():
        text, count = re.subn(rf"^{key}: .*$", f"{key}: {value}", text, flags=re.M)
        assert count == 1, f"{key} is not a line of the example config"
    path.write_text(text, encoding="utf-8")


def start_raw_mcp(
    environment: Mapping[str, str], directory: Path
) -> subprocess.Popen[bytes]:
    """A server that has been through the handshake and is held by the returned
    process: the test can kill it (``SIGKILL``), which the SDK's client does not let
    it do. Close its stdin for a clean exit."""
    process: subprocess.Popen[bytes] = contained_popen(
        [str(SERVER)],
        cwd=directory,
        env=dict(environment),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert process.stdin is not None and process.stdout is not None
    for message in (
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": LATEST_HANDSHAKE_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "raw-client", "version": "0"},
            },
        },
        None,
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    ):
        if message is None:
            assert json.loads(process.stdout.readline())["id"] == 1
            continue
        process.stdin.write(json.dumps(message).encode() + b"\n")
        process.stdin.flush()
    return process
