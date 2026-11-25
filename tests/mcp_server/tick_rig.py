"""Helpers for the three session tick test files (slice 263)."""

import logging
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

import anyio
import pytest

from amoeba.mcp import tick as tick_module
from amoeba.mcp.after_runner import AfterRunner
from amoeba.mcp.channel_event import CHANNEL_METHOD
from amoeba.mcp.presence import (
    PresenceDeps,
    PresenceState,
)
from amoeba.mcp.tick import run_ticks
from amoeba.upstream.context_forge.cli_call import CfRun
from mcp_server.presence_rig import (
    FakeClock,
    Opener,
    RecordingOutbound,
    make_connection,
    make_deps,
    member_state,
)

CLIENT = "claude-code"
#: The constant as the program has it, before the fixture makes it short.
BEFORE_FIRST_REPLY = tick_module.TICK_SECONDS_BEFORE_FIRST_REPLY
#: Planted in a message's text; must never reach the log or the event.
MARKER = "MARKER-TEXT-7f"
#: Ticks a test lets pass to be sure nothing was sent.
QUIET_SECONDS = 0.15


def no_spawn(work: Callable[[], Awaitable[None]]) -> None:
    """A runner that never starts an after-step: the tests here are about the tick."""


async def run_tick(
    deps: PresenceDeps,
    state: PresenceState,
    outbound: RecordingOutbound,
    scenario: Callable[[], Awaitable[None]],
    client: str = CLIENT,
) -> None:
    """Run the tick while ``scenario`` (async) drives it, then cancel it."""
    connection = make_connection(outbound)
    runner = AfterRunner(deps, no_spawn)
    async with anyio.create_task_group() as group:
        group.start_soon(run_ticks, connection, state, deps, client, runner)
        await scenario()
        group.cancel_scope.cancel()


def events_of(outbound: RecordingOutbound) -> list[dict[str, Any]]:
    return [params for method, params in outbound.sent if method == CHANNEL_METHOD]


def setup(
    store_path: Path,
    tmp_path: Path,
    errors: Sequence[Exception | None] = (),
    cf_run: CfRun | None = None,
) -> tuple[PresenceState, PresenceDeps, Opener]:
    clock = FakeClock()
    opener = Opener(store_path, errors=list(errors))
    return (
        member_state(clock, tmp_path),
        make_deps(opener, clock, cf_run=cf_run),
        opener,
    )


def replied(state: PresenceState) -> Callable[[], bool]:
    return lambda: state.as_of_seq is not None


def warnings_of(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
