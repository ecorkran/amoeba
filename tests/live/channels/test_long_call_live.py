"""A tool call that runs past two minutes, in a real Claude Code session (slice 263).

D15 step 1: ``tests/mcp_server/long_call_server.py`` has one tool that waits 220
seconds. The session is asked to call it. The test records what the session showed
at two minutes and whether the marker reached the agent, with no timeout setting of
the session's own, and again with the move to the background turned off. Spend is
pre-authorized for live tiers.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Final

import pytest
from mcp_server.long_call_server import MARKER, SERVER_NAME, TOOL_NAME, WAIT_SECONDS

from live.channels.harness import (
    PROMPTED_CALL_WAIT_SECONDS,
    ClaudeSession,
    SessionError,
)
from live.channels.registration import (
    RegistrationForm,
    ServerRegistration,
    SessionSpec,
)
from live.channels.world import ChannelWorld

SERVER_SCRIPT: Final = (
    Path(__file__).resolve().parents[2] / "mcp_server" / "long_call_server.py"
)
#: The call's time to finish plus one model turn, from the design's 300 seconds.
MARKER_WAIT_SECONDS: Final = 300 + PROMPTED_CALL_WAIT_SECONDS
#: What Claude Code does with a call still running after this long (2.1.212 on).
AUTO_BACKGROUND_SECONDS: Final = 120
AUTO_BACKGROUND_VARIABLE: Final = "CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS"
PROMPT: Final = (
    f"Call the {TOOL_NAME} tool of the {SERVER_NAME} server once and wait for its "
    "result. Then reply with the exact text it returned and nothing else."
)
#: What D15 step 1 records: three results.
ARRIVED_PLAIN: Final = "marker reached the agent with no setting"
ARRIVED_WITH_SETTING: Final = "marker reached the agent with the background move off"
NEVER_ARRIVED: Final = "marker never reached the agent"


def _session(world: ChannelWorld, extra: dict[str, str]) -> ClaudeSession:
    directory = world.outside
    spec = SessionSpec(
        cwd=directory,
        model=world.model,
        registration=ServerRegistration(
            SERVER_NAME, sys.executable, (str(SERVER_SCRIPT),)
        ),
        form=RegistrationForm.PROJECT_MCP_JSON,
        allowed_tools=(f"mcp__{SERVER_NAME}__{TOOL_NAME}",),
        scratch=world.scratch,
        environ=world.forge.environ,
        extra_environment=extra,
        as_channel=False,
    )
    return ClaudeSession(spec)


def _run_once(world: ChannelWorld, extra: dict[str, str]) -> tuple[str, float, str]:
    """Ask for the call; the screen at two minutes, the seconds to the marker, or -1."""
    session = _session(world, extra)
    session.start()
    try:
        asked = session.screen.mark()
        started = time.monotonic()
        session.type_prompt(PROMPT)
        time.sleep(AUTO_BACKGROUND_SECONDS)
        at_two_minutes = session.last_screen()
        try:
            session.wait_for(MARKER, MARKER_WAIT_SECONDS, since=asked)
        except SessionError:
            # The marker never showed: that is a result of this test, not a failure.
            return at_two_minutes, -1.0, session.last_screen()
        return at_two_minutes, time.monotonic() - started, session.last_screen()
    finally:
        session.terminate()


def test_a_call_past_two_minutes_reaches_the_agent(
    channel_world: ChannelWorld, capsys: pytest.CaptureFixture[str]
) -> None:
    screen, seconds, final = _run_once(channel_world, {})
    result = ARRIVED_PLAIN
    if seconds < 0:
        screen, seconds, final = _run_once(
            channel_world, {AUTO_BACKGROUND_VARIABLE: "0"}
        )
        result = NEVER_ARRIVED if seconds < 0 else ARRIVED_WITH_SETTING
    with capsys.disabled():
        print(f"\nLONG-CALL RESULT: {result}; marker after {seconds:.0f}s")
        print(f"SCREEN AT TWO MINUTES:\n{screen[-1500:]}")
        print(f"FINAL SCREEN:\n{final[-1500:]}")
    assert WAIT_SECONDS > AUTO_BACKGROUND_SECONDS
    assert result != NEVER_ARRIVED
