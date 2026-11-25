"""Push to a real Claude Code session across two machines (slice 263, 8.7, D15).

The two-machine fixture (``two_machine_hub``): a real hub, ``alpha`` and ``beta`` each
with its own home and stub ``cf``. The session is a real Claude Code in the receiver's
repo on ``beta``, its server started by a launcher that gives it ``beta``'s home. The
request is sent with ``amoeba send`` from a repo on ``alpha``. Spend is pre-authorized
for live tiers.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

import pytest
from hub.sessions_support import (
    PROGRAM,
    RECEIVER,
    RECEIVER_ORIGIN,
    SENDER,
    SENDER_ORIGIN,
)
from hub_fixture import FIRST, SECOND, ClientHome, FixtureHub, two_machine_hub
from hub_mcp import set_hub_timings

from live.channels.harness import (
    INBOX_CALL_WAIT_SECONDS,
    STALE_MARGIN_SECONDS,
    STARTUP_SCREEN_WAIT_SECONDS,
    ClaudeSession,
)
from live.channels.registration import ServerRegistration, SessionSpec
from live.channels.world import (
    ALLOWED_TOOLS,
    FORM,
    SERVER_NAME,
    wait_for_log,
    wait_until,
)

AMOEBA_MCP: Final = Path(sys.executable).with_name("amoeba-mcp")
#: Short intervals, so a test waits seconds.
TIMINGS: Final = {
    "notify_poll_seconds": 1,
    "session_heartbeat_seconds": 1,
    "session_stale_seconds": 3,
}
HEARTBEAT_WAIT: Final = TIMINGS["session_heartbeat_seconds"] + STALE_MARGIN_SECONDS


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[FixtureHub]:
    with two_machine_hub(tmp_path) as running:
        yield running


def _launcher(hub: FixtureHub, beta: ClientHome, scratch: Path) -> tuple[Path, Path]:
    """A script that gives the server ``beta``'s home, ``cf`` and ``PATH``, and appends
    its stderr to a log the test reads; the script and the log."""
    log = scratch / "beta.server.log"
    script = scratch / "beta.launch.sh"
    exports = "\n".join(
        f"export {name}='{value}'" for name, value in hub.env_for(beta.home).items()
    )
    script.write_text(
        f"#!/bin/sh\n{exports}\nexec '{AMOEBA_MCP}' 2>> '{log}'\n", encoding="utf-8"
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script, log


def _sessions(alpha: ClientHome) -> list[dict[str, Any]]:
    done = alpha.run("list", "-j")
    assert done.code == 0, done.err + done.out
    listed = json.loads(done.out)
    return [
        session
        for program in listed["programs"]
        for member in program["members"]
        for session in member["sessions"]
    ]


def test_a_request_from_alpha_reaches_a_real_session_on_beta_and_confirms_push(
    hub: FixtureHub, tmp_path: Path, channel_model: str
) -> None:
    set_hub_timings(hub, **TIMINGS)
    alpha, beta = hub.clients[FIRST], hub.clients[SECOND]
    sender = alpha.clone(SENDER, SENDER_ORIGIN, "cf-sender", SENDER)
    receiver = beta.clone(RECEIVER, RECEIVER_ORIGIN, "cf-receiver", RECEIVER)
    for client, repo in ((alpha, sender), (beta, receiver)):
        done = client.run_in(repo, "add", "--program", PROGRAM, "-j")
        assert done.code == 0, done.err + done.out
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    script, log = _launcher(hub, beta, scratch)
    session = ClaudeSession(
        SessionSpec(
            cwd=receiver,
            model=channel_model,
            registration=ServerRegistration(SERVER_NAME, str(script)),
            form=FORM,
            allowed_tools=ALLOWED_TOOLS,
            scratch=scratch,
            environ=os.environ,
        )
    )
    session.start()
    try:
        wait_until(
            session,
            lambda: any(s["machine"] == SECOND for s in _sessions(alpha)),
            "the session on beta in list -j from alpha",
            STARTUP_SCREEN_WAIT_SECONDS,
        )
        wait_for_log(session, log, f"machine {SECOND}", STARTUP_SCREEN_WAIT_SECONDS)

        sent = alpha.run_in(
            sender,
            "send",
            "--to",
            RECEIVER,
            "--id",
            "live-1",
            "--subject",
            "Need X",
            "--body",
            "Please add X",
            "-j",
        )
        assert sent.code == 0, sent.err + sent.out

        wait_for_log(session, log, "tool inbox called", INBOX_CALL_WAIT_SECONDS)
        wait_until(
            session,
            lambda: any(s["push_confirmed_at"] for s in _sessions(alpha)),
            "push_confirmed_at in list -j from the sending machine",
            HEARTBEAT_WAIT,
        )
    finally:
        session.terminate()
