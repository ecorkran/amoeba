"""Start a detached child and stop it with everything it started (slice 223, D6).

A thin wrapper over the kept ``upstream.squadron.launch.spawn``, which already does
the detached start: exclusive logs, a session of its own, no stdin, the inherited
environment. This module adds what the kept ``ChildHandle`` (``poll`` only) lacks: a
child that can be waited on, and a stop that reaches the child's own children. It
imports nothing from Amoeba but ``upstream.squadron`` (``launch`` and its fault
vocabulary).
"""

from __future__ import annotations

import os
import signal
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final, Protocol

from amoeba.upstream.squadron.faults import LaunchFailure
from amoeba.upstream.squadron.launch import (
    LaunchError,
    LaunchLogs,
    spawn,
)

#: How long a stopped child gets to exit after SIGTERM before it is killed.
TERMINATE_GRACE_SECONDS: Final = 5.0


class WaitableChild(Protocol):
    """The part of a ``subprocess.Popen`` the operations use; ``Popen`` satisfies it."""

    @property
    def pid(self) -> int: ...

    def poll(self) -> int | None:
        """The exit code, or ``None`` while the child runs."""
        ...

    def wait(self, timeout: float | None = None) -> int:
        """The exit code; raises ``subprocess.TimeoutExpired`` if it runs on."""
        ...


#: Starts a child process: ``subprocess.Popen`` in production, a fake in tests.
type WaitablePopen = Callable[..., WaitableChild]

#: Starts a child in a directory with its logs: ``start_child`` in production, a
#: fake in unit tests.
type Spawner = Callable[[Sequence[str], Path, LaunchLogs], WaitableChild | LaunchError]


def start_child(
    argv: Sequence[str],
    cwd: Path,
    logs: LaunchLogs,
    popen: WaitablePopen = subprocess.Popen,
) -> WaitableChild | LaunchError:
    """Start ``argv`` in ``cwd``, logging to ``logs``; the logs' directories are made.

    ``popen`` is the factory the kept ``spawn`` starts the child with:
    ``subprocess.Popen`` in production.

    Returns:
        The child, or the kept ``LaunchError`` when a log or the child cannot be
        created (including a log that already exists).
    """
    try:
        for directory in {logs.stdout.parent, logs.stderr.parent}:
            directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        # An expected external failure (permissions, a full disk): an answer for
        # the caller to record, not a bug. Reported the way ``spawn`` reports one.
        return spawn_failure(error)
    # The kept ``spawn`` hands back a ``ChildHandle`` (``poll`` only); keep the
    # waitable child the factory made, so no type is narrowed after the fact.
    made: list[WaitableChild] = []

    def recording_popen(*args: Any, **kwargs: Any) -> WaitableChild:
        child = popen(*args, **kwargs)
        made.append(child)
        return child

    started = spawn(argv, str(cwd), logs, recording_popen)
    if isinstance(started, LaunchError):
        return started
    return made[0]


def spawn_failure(error: OSError) -> LaunchError:
    """The kept launch error for an ``OSError`` before the child started."""
    return LaunchError(LaunchFailure.SPAWN_ERROR, f"{type(error).__name__}: {error}")


def terminate_group(child: WaitableChild) -> None:
    """Stop the child's whole process group, then wait for the child to exit.

    The child leads its own session (``start_new_session``), so its group is its
    pid. SIGTERM first; SIGKILL if it has not exited after the grace period.
    """
    for sending in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(child.pid, sending)
        except ProcessLookupError:
            # Expected: the group is already gone, which is what was wanted.
            child.wait()
            return
        try:
            child.wait(timeout=TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            # Expected: it ignored SIGTERM; the loop goes on to SIGKILL.
            continue
        return
    child.wait()
