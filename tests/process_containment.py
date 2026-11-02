"""Keep every process a test starts from outliving it or filling a disk.

Two protections, both mechanical:

* **A file-size cap.** :func:`contained_popen` starts a child with ``RLIMIT_FSIZE``
  set, so no file it writes (a log, a database, a stub's call log) can grow past
  :data:`FILE_SIZE_LIMIT_BYTES`. The kernel enforces it: a child that crosses it dies
  with SIGXFSZ, loudly, instead of writing until the disk is full. A resident process
  looping on a fault once wrote over 600 GB to its log this way.
* **No survivors.** Teardown fixtures do not run when pytest itself is killed, and a
  killed run leaves its children behind, running. :func:`contained_popen` registers
  each child and kills the live ones at interpreter exit, and
  :func:`reap_orphans` (run at every session start) kills what an earlier,
  killed session left: processes re-parented to ``init`` whose command line names
  this user's pytest temp directory.

``tests/test_process_containment.py`` fails if a test module starts a process any
other way.
"""

from __future__ import annotations

import atexit
import getpass
import os
import re
import resource
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final

#: The largest file any test child may write. Defined once.
FILE_SIZE_LIMIT_BYTES: Final = 256 * 1024 * 1024

#: A leaked process is only reaped once it is this old, so another session's
#: freshly orphaned child (a stub ``sq`` whose parent was killed on purpose) is
#: left alone.
MIN_ORPHAN_AGE_SECONDS: Final = 300

#: Seconds between SIGTERM and SIGKILL when reaping.
REAP_GRACE_SECONDS: Final = 2.0

_INIT_PID: Final = 1
_PS_COMMAND: Final = ("ps", "-axo", "pid=,ppid=,etime=,command=")
_PS_LINE: Final = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\S+)\s+(.*)$")

_children: list[subprocess.Popen[Any]] = []


def contained_popen(
    *args: Any, file_size_limit_bytes: int = FILE_SIZE_LIMIT_BYTES, **kwargs: Any
) -> subprocess.Popen[Any]:
    """``subprocess.Popen`` with a file-size cap, killed at interpreter exit."""
    if "preexec_fn" in kwargs:
        raise ValueError("contained_popen sets preexec_fn itself")

    def limit_file_size() -> None:
        resource.setrlimit(
            resource.RLIMIT_FSIZE, (file_size_limit_bytes, file_size_limit_bytes)
        )

    child = subprocess.Popen(*args, preexec_fn=limit_file_size, **kwargs)  # noqa: PLW1509
    _children.append(child)
    return child


def kill_children() -> None:
    """Kill every child this process started that is still alive."""
    for child in _children:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=REAP_GRACE_SECONDS * 5)
    _children.clear()


atexit.register(kill_children)


def pytest_temp_root() -> Path:
    """Where pytest keeps this user's temp directories."""
    return Path(tempfile.gettempdir()).resolve() / f"pytest-of-{getpass.getuser()}"


def _etime_seconds(text: str) -> int:
    """Seconds in ``ps`` elapsed time: ``[[dd-]hh:]mm:ss``."""
    days, _, clock = text.rpartition("-")
    parts = [int(part) for part in clock.split(":")]
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds + (int(days) * 86400 if days else 0)


def leaked_pids(listing: str, *, root: Path) -> list[int]:
    """Pids in a ``ps`` listing that an earlier killed session left running."""
    found: list[int] = []
    for line in listing.splitlines():
        match = _PS_LINE.match(line)
        if match is None:
            continue
        pid, parent, elapsed, command = match.groups()
        if (
            int(parent) == _INIT_PID
            and str(root) in command
            and _etime_seconds(elapsed) >= MIN_ORPHAN_AGE_SECONDS
        ):
            found.append(int(pid))
    return found


def _ps_listing() -> str:
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        _PS_COMMAND, capture_output=True, text=True, check=True, timeout=30
    ).stdout


def _terminate(pid: int) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return  # already gone: the goal state
        deadline = time.monotonic() + REAP_GRACE_SECONDS
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.05)


def reap_orphans(
    listing: Callable[[], str] = _ps_listing,
    terminate: Callable[[int], None] = _terminate,
    root: Path | None = None,
) -> Sequence[int]:
    """Kill processes an earlier, killed test session left behind; return their pids."""
    pids = leaked_pids(listing(), root=root or pytest_temp_root())
    for pid in pids:
        terminate(pid)
    return pids
