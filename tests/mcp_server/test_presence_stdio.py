"""Presence over real stdio: the installed ``amoeba-mcp`` (slice 241, D6, 9.3).

A throwaway ``AMOEBA_HOME`` with this repo registered, a fake ``cf`` on ``PATH`` and
short intervals. A clean exit deletes the session row; a SIGKILLed server leaves one
that stops counting after ``session_stale_seconds`` and that another server's
heartbeat deletes.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

import anyio
import pytest
from cf_fixtures import DEFAULT_WORKTREE, write_fake_cf_with_projects
from cli.cli_support import run_amoeba, write_config
from live_environment import process_environment
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp_types.version import LATEST_HANDSHAKE_VERSION
from process_containment import contained_popen
from user_configs import example_config_text

from amoeba.cli.exit_codes import EXIT_OK
from mcp_server.presence_rig import all_session_rows, eventually, sessions_in

SERVER: Final = Path(sys.executable).with_name("amoeba-mcp")
POLL_SECONDS: Final = 0.1
HEARTBEAT_SECONDS: Final = 0.2
STALE_SECONDS: Final = 1.0
WAIT_SECONDS: Final = 30.0
TIMINGS: Final = {
    "notify_poll_seconds": POLL_SECONDS,
    "session_heartbeat_seconds": HEARTBEAT_SECONDS,
    "session_stale_seconds": STALE_SECONDS,
}


def _short_interval_config() -> str:
    text = example_config_text()
    for key, value in TIMINGS.items():
        text = re.sub(rf"^{key}: .*$", f"{key}: {value}", text, flags=re.MULTILINE)
    return text


@pytest.fixture
def world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, str]]:
    """The store path, and the environment a server started in ``tmp_path`` gets."""
    bin_dir = tmp_path / "bin"
    write_fake_cf_with_projects(bin_dir, DEFAULT_WORKTREE)
    path_value = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
    monkeypatch.setenv("PATH", path_value)
    write_config(_short_interval_config())
    assert run_amoeba(tmp_path, "add").returncode == EXIT_OK
    home = os.environ["AMOEBA_HOME"]
    environment = process_environment(os.environ, PATH=path_value, AMOEBA_HOME=home)
    return Path(home) / "amoeba.sqlite3", environment


def _wait_until(condition: Any, what: str) -> None:
    deadline = time.monotonic() + WAIT_SECONDS
    while not condition():
        assert time.monotonic() < deadline, f"waited {WAIT_SECONDS}s for {what}"
        time.sleep(0.05)


def test_a_member_server_has_a_row_while_serving_and_none_after_stdin_closes(
    world: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    store_path, environment = world
    parameters = StdioServerParameters(
        command=str(SERVER), args=[], env=environment, cwd=tmp_path
    )
    seen: list[int] = []

    async def serve() -> None:
        with anyio.fail_after(WAIT_SECONDS):
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    await eventually(
                        lambda: bool(all_session_rows(store_path)), "the row"
                    )
                    seen.append(len(all_session_rows(store_path)))

    anyio.run(serve)

    assert seen == [1]
    _wait_until(lambda: not all_session_rows(store_path), "the row deleted on exit")


def _start_raw_server(
    cwd: Path, environment: dict[str, str]
) -> subprocess.Popen[bytes]:
    """A server that has been through the handshake, as a client leaves it."""
    process: subprocess.Popen[bytes] = contained_popen(
        [str(SERVER)],
        cwd=cwd,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert process.stdin is not None and process.stdout is not None
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": LATEST_HANDSHAKE_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "raw-client", "version": "0"},
        },
    }
    process.stdin.write(json.dumps(initialize).encode() + b"\n")
    process.stdin.flush()
    assert json.loads(process.stdout.readline())["id"] == 1
    initialized = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    process.stdin.write(json.dumps(initialized).encode() + b"\n")
    process.stdin.flush()
    return process


def test_a_killed_servers_row_goes_stale_and_another_servers_beat_deletes_it(
    world: tuple[Path, dict[str, str]], tmp_path: Path
) -> None:
    store_path, environment = world
    killed = _start_raw_server(tmp_path, environment)
    _wait_until(lambda: bool(all_session_rows(store_path)), "the first server's row")
    (dead_row,) = all_session_rows(store_path)

    os.kill(killed.pid, signal.SIGKILL)
    killed.wait(timeout=WAIT_SECONDS)

    assert all_session_rows(store_path) == [dead_row]
    later = datetime.now(UTC) + timedelta(seconds=STALE_SECONDS)
    assert sessions_in(store_path, later, STALE_SECONDS) == ()

    time.sleep(STALE_SECONDS)
    second = _start_raw_server(tmp_path, environment)
    try:
        _wait_until(
            lambda: dead_row[0] not in [row[0] for row in all_session_rows(store_path)],
            "the second server's beat to prune the dead row",
        )
        assert len(all_session_rows(store_path)) == 1
    finally:
        assert second.stdin is not None
        second.stdin.close()
        second.wait(timeout=WAIT_SECONDS)
