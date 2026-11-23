"""A claimed wake row, short commands and a settable clock for the wrapper tests
(slice 244, D6)."""

from __future__ import annotations

import os
import shlex
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any

from store.message_support import ADDRESSEE, NOW, seed_members
from store.wake_support import seed_waking_member
from store_open import open_local_store

from amoeba.operations.processes import WaitableChild
from amoeba.store.models import Wake
from amoeba.store.store import Store
from amoeba.store.wakes import WakeLimits, claim_wake, get_wake

#: Short enough that a test waiting out a timeout waits this much real time.
TEST_WAKE_TIMEOUT_SECONDS = 1.0
#: How long a test waits for a process to be gone, and how often it looks.
GONE_WAIT_SECONDS = 10.0
POLL_SECONDS = 0.05
WAKE_ID = "wake-under-test"

#: Writes what the command saw to the file named by its first argument, spawns a
#: grandchild in its group when asked, and exits with the code of its third argument.
PROBE = dedent(
    """
    import json, os, subprocess, sys, time
    # A group member that ignores SIGTERM and writes its pid, as ready, to its argument.
    STUBBORN = (
        "import os, signal, sys, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "open(sys.argv[1], 'w').write(str(os.getpid())); time.sleep(60)"
    )
    out, grandchild_file, code, mode = sys.argv[1:5]
    seen = {"cwd": os.getcwd(), "env": dict(os.environ), "stdin": sys.stdin.read()}
    with open(out, "w") as handle:
        json.dump(seen, handle)
    if mode in ("grandchild", "grandchild-sleep"):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        with open(grandchild_file, "w") as handle:
            handle.write(str(child.pid))
    if mode == "stubborn":
        # A group member that ignores SIGTERM, ready before the leader sleeps.
        child = subprocess.Popen([sys.executable, "-c", STUBBORN, grandchild_file])
        while not os.path.exists(grandchild_file):
            time.sleep(0.02)
    if mode in ("sleep", "grandchild-sleep", "stubborn"):
        time.sleep(60)
    sys.exit(int(code))
    """
)


def write_probe(tmp_path: Path) -> Path:
    path = tmp_path / "probe.py"
    path.write_text(PROBE, encoding="utf-8")
    return path


def probe_command(tmp_path: Path, *, code: int = 0, mode: str = "plain") -> str:
    """The command text that runs the probe; its output files are in ``tmp_path``."""
    return shlex.join(
        [
            sys.executable,
            str(write_probe(tmp_path)),
            str(tmp_path / "seen.json"),
            str(tmp_path / "grandchild.pid"),
            str(code),
            mode,
        ]
    )


def claimed_store(
    tmp_path: Path,
    command: str,
    *,
    directory: Path | None = None,
    wake_id: str = WAKE_ID,
    database: Path | None = None,
    claimed_at: datetime = NOW,
    timeout_seconds: float = TEST_WAKE_TIMEOUT_SECONDS,
) -> tuple[Store, Wake]:
    """A store holding a claimed, unended row for ``command``, run in ``directory``
    (default: a new ``checkout`` directory), in ``database`` (default:
    ``amoeba.sqlite3`` under ``tmp_path``). The row is claimed at ``claimed_at`` with
    a deadline ``timeout_seconds`` later."""
    checkout = directory
    if checkout is None:
        checkout = tmp_path / "checkout"
        checkout.mkdir(exist_ok=True)
    store = open_local_store(
        tmp_path / "amoeba.sqlite3" if database is None else database
    )
    with store.write() as transaction:
        seed_members(transaction)
        seed_waking_member(transaction, ADDRESSEE, command, str(checkout))
        claimed = claim_wake(
            transaction,
            ADDRESSEE,
            claimed_at,
            WakeLimits(
                timeout_seconds=timeout_seconds,
                max_per_day=3,
                session_stale_seconds=90,
            ),
            wake_id,
            str(tmp_path / "logs" / wake_id),
        )
        assert claimed is not None
    return store, claimed


def row_of(store: Store, wake_id: str = WAKE_ID) -> Wake:
    with store.read() as transaction:
        wake = get_wake(transaction, wake_id)
    assert wake is not None
    return wake


def stored_row(tmp_path: Path, wake_id: str = WAKE_ID) -> Wake:
    """The row as the store file holds it now, read through a fresh connection."""
    with open_local_store(tmp_path / "amoeba.sqlite3") as reopened:
        return row_of(reopened, wake_id)


def wait_until(condition: Callable[[], bool]) -> bool:
    """Poll ``condition`` until it holds or ``GONE_WAIT_SECONDS`` pass."""
    deadline = time.monotonic() + GONE_WAIT_SECONDS
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(POLL_SECONDS)
    return condition()


def process_is_gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


class RaisingWaitChild:
    """A real started child whose first ``wait`` raises, as a wrapper bug would."""

    def __init__(self, child: WaitableChild, message: str) -> None:
        self._child = child
        self._message = message
        self._raised = False

    @property
    def pid(self) -> int:
        return self._child.pid

    def poll(self) -> int | None:
        return self._child.poll()

    def wait(self, timeout: float | None = None) -> int:
        if not self._raised:
            self._raised = True
            raise RuntimeError(self._message)
        return self._child.wait(timeout=timeout)


def popen_failing_on_wait(message: str, started: Callable[..., WaitableChild]) -> Any:
    """A ``popen`` that starts the command with ``started`` and wraps the child in a
    ``RaisingWaitChild``."""

    def popen(*args: Any, **kwargs: Any) -> WaitableChild:
        return RaisingWaitChild(started(*args, **kwargs), message)

    return popen
