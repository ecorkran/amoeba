"""The channels tier's fixture world (slice 241, D10, 11.1).

Two members of one program, ``cf-s`` and ``sq-s``, built through the real ``cf`` in
the pause tier's throwaway data directory and registered with ``add``; and
``outside``, a git repo that is neither a Context Forge project nor a member. Each
session directory carries the adopted registration (a project ``.mcp.json``, task
1.2) naming a launcher that records the server's pid and appends its stderr to a log
the test reads.
"""

from __future__ import annotations

import json
import stat
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml
from git_repo import git

from live.channels.harness import (
    ClaudeSession,
    SessionError,
)
from live.channels.registration import RegistrationForm, ServerRegistration, SessionSpec
from live.messaging.repos import build_repo
from live.pause.harness import PauseWorld, run_amoeba

AMOEBA_MCP: Final = Path(sys.executable).with_name("amoeba-mcp")
SERVER_NAME: Final = "amoeba"
FORGE: Final = "cf-s"
SQUADRON: Final = "sq-s"
OUTSIDE: Final = "outside"
#: The adopted registration form (task 1.2, observed 20261116).
FORM: Final = RegistrationForm.PROJECT_MCP_JSON
#: ``amoeba-mcp`` refuses a ``resume_wait_seconds`` whose ``answer`` bound reaches its
#: call deadline, so the world's config is lowered from the pause tier's value, as
#: the MCP and messaging tiers do.
RESUME_WAIT_SECONDS: Final = 60
#: Short intervals, so a test waits seconds (D10).
TIMINGS: Final = {
    "notify_poll_seconds": 1,
    "session_heartbeat_seconds": 1,
    "session_stale_seconds": 3,
}
ALLOWED_TOOLS: Final = (f"mcp__{SERVER_NAME}__inbox", f"mcp__{SERVER_NAME}__list")
#: The variables ``amoeba-mcp`` needs to find the throwaway store and ``cf`` data.
SERVER_VARIABLES: Final = ("AMOEBA_HOME", "CONTEXT_FORGE_DATA_DIR")
POLL_SECONDS: Final = 0.5


@dataclass(frozen=True)
class ChannelWorld:
    forge: PauseWorld
    squadron: PauseWorld
    outside: Path
    scratch: Path
    model: str


def build_channel_world(parent: Path, base: PauseWorld, model: str) -> ChannelWorld:
    forge = build_repo(parent, base, FORGE)
    squadron = build_repo(parent, base, SQUADRON)
    outside = parent / OUTSIDE
    outside.mkdir()
    git(outside, "init", "-q", "-b", "main")
    (outside / "README.md").write_text("outside\n", encoding="utf-8")
    git(outside, "add", "-A")
    git(outside, "commit", "-q", "-m", "seed")
    config_path = base.amoeba_home / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config.update(TIMINGS, resume_wait_seconds=RESUME_WAIT_SECONDS)
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    scratch = parent / "scratch"
    scratch.mkdir()
    return ChannelWorld(forge, squadron, outside, scratch, model)


def launcher(world: ChannelWorld, name: str) -> tuple[Path, Path, Path]:
    """A launcher for one session: its script, its server log and its pid file."""
    log = world.scratch / f"{name}.server.log"
    pid_file = world.scratch / f"{name}.server.pid"
    script = world.scratch / f"{name}.launch.sh"
    script.write_text(
        f"#!/bin/sh\necho $$ > '{pid_file}'\nexec '{AMOEBA_MCP}' 2>> '{log}'\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script, log, pid_file


def session_in(
    world: ChannelWorld, directory: Path, name: str
) -> tuple[ClaudeSession, Path, Path]:
    """A session, not yet started, in ``directory``; its server log and pid file."""
    script, log, pid_file = launcher(world, name)
    variables = {key: world.forge.environ[key] for key in SERVER_VARIABLES}
    spec = SessionSpec(
        cwd=directory,
        model=world.model,
        registration=ServerRegistration(SERVER_NAME, str(script), (), variables),
        form=FORM,
        allowed_tools=ALLOWED_TOOLS,
        scratch=world.scratch,
        environ=world.forge.environ,
        extra_environment=variables,
    )
    return ClaudeSession(spec), log, pid_file


def wait_for_log(session: ClaudeSession, log: Path, text: str, timeout: float) -> str:
    """Wait until ``text`` is in the server log; the matching line."""
    deadline = time.monotonic() + timeout
    while True:
        lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        found = [line for line in lines if text in line]
        if found:
            return found[0]
        if time.monotonic() > deadline:
            tail = "\n".join(lines[-20:])
            raise SessionError(
                f"waited {timeout}s for {text!r} in the server log; log tail:\n{tail}\n"
                f"last screen:\n{session.last_screen()}"
            )
        time.sleep(POLL_SECONDS)


def sessions_of(world: ChannelWorld, member: str) -> list[dict[str, Any]]:
    """``amoeba list -j``'s sessions under the member named ``member``."""
    listed = run_amoeba(world.forge, "list")
    assert listed.returncode == 0, listed.stderr + listed.stdout
    document = json.loads(listed.stdout)
    for program in document["programs"]:
        for entry in program["members"]:
            if entry["member"]["name"] == member:
                sessions: list[dict[str, Any]] = entry["sessions"]
                return sessions
    raise AssertionError(f"list shows no member named {member}")


def all_sessions(world: ChannelWorld) -> list[dict[str, Any]]:
    listed = run_amoeba(world.forge, "list")
    assert listed.returncode == 0, listed.stderr + listed.stdout
    document = json.loads(listed.stdout)
    return [
        session
        for program in document["programs"]
        for entry in program["members"]
        for session in entry["sessions"]
    ]


def wait_until(
    session: ClaudeSession, condition: Callable[[], bool], what: str, timeout: float
) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise SessionError(
                f"waited {timeout}s for {what}; last screen:\n{session.last_screen()}"
            )
        time.sleep(POLL_SECONDS)
