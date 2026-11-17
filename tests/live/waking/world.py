"""A sender and a woken member in one program, and the calls the waking tier makes
(slice 244, 9.2).

The pause tier's member plays the sender; a second committed git repo, a Context Forge
project in the same throwaway data directory, is the member that gets woken. No model
runs: the wake command is ``fixture_agent.py`` or ``recorder_command.py``. Every
``amoeba`` call goes by the absolute script beside ``sys.executable`` with the world's
throwaway ``AMOEBA_HOME``, and the ``PATH`` of those calls starts with that script's
directory, so the wrapper (which keeps ``PATH``) and the fixture agent's own ``amoeba``
calls reach the same build and the same store. Every wait is a bounded poll.
"""

from __future__ import annotations

import dataclasses
import os
import shlex
import signal
import sqlite3
import sys
import time
from collections.abc import Callable, Generator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from live.messaging.repos import build_repo
from live.pause.harness import PauseWorld, result_of, run_amoeba

FIXTURE_AGENT: Final = Path(__file__).parent / "fixture_agent.py"
RECORDER: Final = Path(__file__).parent / "recorder_command.py"
RECIPIENT_NAME: Final = "wake-s"
#: The two keys the contract's example holds with suggested values; this tier's own
#: copy of the config replaces them so a case runs in seconds.
WAKE_TIMEOUT_SECONDS: Final = 5
MAX_WAKES_PER_DAY: Final = 2
#: The fixture agent's own cap, well past any case's own wait.
AGENT_CAP_SECONDS: Final = 60
POLL_SECONDS: Final = 0.2
WAIT_SECONDS: Final = 60.0
#: How a wake's end is awaited after the timeout has had time to pass.
TIMEOUT_WAIT_SECONDS: Final = WAKE_TIMEOUT_SECONDS + 30.0
WAKE_COLUMNS: Final = (
    "wake_id, outcome, exit_code, detail, command_pid, ended_at, deadline_at, log_stem"
)


@dataclass(frozen=True)
class WakingWorld:
    """The sender's world, the woken member's, and the processes to clean up."""

    sender: PauseWorld
    recipient: PauseWorld
    command_pids: list[int]


@dataclass(frozen=True)
class WakeRow:
    wake_id: str
    outcome: str | None
    exit_code: int | None
    detail: str | None
    command_pid: int | None
    ended_at: str | None
    deadline_at: str
    log_stem: str | None


def _with_path_first(world: PauseWorld) -> PauseWorld:
    """``world`` whose calls find the ``amoeba`` of this build first on ``PATH``."""
    bin_dir = str(Path(sys.executable).parent)
    path = bin_dir + os.pathsep + world.environ["PATH"]
    return dataclasses.replace(world, environ={**world.environ, "PATH": path})


def _write_wake_limits(world: PauseWorld) -> None:
    """This tier's own copy of the config: the example's values for everything else."""
    path = world.amoeba_home / "config.yaml"
    config: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    config.update(
        wake_timeout_seconds=WAKE_TIMEOUT_SECONDS, max_wakes_per_day=MAX_WAKES_PER_DAY
    )
    path.write_text(yaml.safe_dump(config), encoding="utf-8")


def build_waking_world(parent: Path, base: PauseWorld) -> WakingWorld:
    recipient = build_repo(parent, base, RECIPIENT_NAME)
    _write_wake_limits(base)
    return WakingWorld(_with_path_first(base), _with_path_first(recipient), [])


def agent_command(world: WakingWorld, *flags: str) -> str:
    """The wake command that runs the fixture agent with its own cap, plus the case's
    ``flags``. The throwaway Context Forge data directory reaches it through the wake
    environment, as a real agent's would."""
    return shlex.join(
        [
            sys.executable,
            str(FIXTURE_AGENT),
            "--max-seconds",
            str(AGENT_CAP_SECONDS),
            *flags,
        ]
    )


def amoeba(
    world: PauseWorld, *arguments: str, expect: int = 0, cwd: Path | None = None
) -> dict[str, Any]:
    """``amoeba <arguments> -j`` in ``world``'s checkout; the document, after checking
    the exit code."""
    completed = run_amoeba(world, *arguments, cwd=cwd)
    assert completed.returncode == expect, (
        f"amoeba {' '.join(arguments)} exited {completed.returncode}\n"
        f"{completed.stdout}\n{completed.stderr}"
    )
    return dict(result_of(completed))


def set_wake_command(world: WakingWorld, command: str) -> None:
    amoeba(world.recipient, "add", "--wake-command", command)


def send(
    world: WakingWorld, request_id: str, *extra: str, kind_note: bool = False
) -> dict[str, Any]:
    arguments = ["send", "--id", request_id, "--to", RECIPIENT_NAME]
    if kind_note:
        arguments.insert(1, "--note")
    arguments += [
        "--subject",
        f"subject of {request_id}",
        "--body",
        f"body of {request_id}",
        *extra,
    ]
    return amoeba(world.sender, *arguments)


def wake_rows(world: WakingWorld) -> list[WakeRow]:
    """Every ``wakes`` row of the throwaway store, oldest first (a read-only look)."""
    uri = f"file:{world.sender.store}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        rows = connection.execute(
            f"SELECT {WAKE_COLUMNS} FROM wakes ORDER BY started_at"
        ).fetchall()
    return [WakeRow(*row) for row in rows]


def wait_until(
    condition: Callable[[], bool], what: str, seconds: float = WAIT_SECONDS
) -> None:
    """Poll ``condition`` until it holds; failing, say what was awaited."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(POLL_SECONDS)
    assert condition(), f"gave up waiting {seconds:g} s for {what}"


def wait_for_row(
    world: WakingWorld, predicate: Callable[[WakeRow], bool], what: str, seconds: float
) -> WakeRow:
    found: list[WakeRow] = []

    def seen() -> bool:
        found[:] = [row for row in wake_rows(world) if predicate(row)]
        return bool(found)

    wait_until(seen, what, seconds)
    return found[0]


def wait_for_end(world: WakingWorld, index: int = 0) -> WakeRow:
    """The ``index``-th wake once it is recorded as ended."""

    def ended() -> bool:
        rows = wake_rows(world)
        return len(rows) > index and rows[index].ended_at is not None

    wait_until(ended, f"wake {index} to end", TIMEOUT_WAIT_SECONDS)
    return wake_rows(world)[index]


def member_wake(world: WakingWorld) -> dict[str, Any] | None:
    """The woken member's ``wake`` object in ``list -j``."""
    listed = amoeba(world.sender, "list")
    members = [
        member
        for program in listed["programs"]
        for member in program["members"]
        if member["member"]["name"] == RECIPIENT_NAME
    ]
    (member,) = members
    wake: dict[str, Any] | None = member["wake"]
    return wake


def request_states(world: WakingWorld) -> dict[str, str]:
    """The sender's requests by id and state, from its ``inbox``."""
    inbox = amoeba(world.sender, "inbox")
    return {request["id"]: request["state"] for request in inbox["requests"]}


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    return True


@contextmanager
def reaping(world: WakingWorld) -> Generator[WakingWorld]:
    """Whatever a case leaves running is stopped, its whole group, when it ends."""
    try:
        yield world
    finally:
        pids = {*world.command_pids, *(r.command_pid or 0 for r in wake_rows(world))}
        for pid in pids - {0}:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                # Expected: the command already ended, which is what the case wants.
                continue
