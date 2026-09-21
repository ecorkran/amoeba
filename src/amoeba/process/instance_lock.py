"""Single-instance enforcement: an advisory file lock, and a PID file beside it.

**The lock is the truth about liveness.** The kernel releases an advisory
``flock`` when the holder dies by any means — normal exit, ``SIGKILL``, a panic,
a power loss — so a stale lock cannot exist and nothing ever needs to clean one
up. That is what makes the crash-only claim work: after ``kill -9``, the next
start acquires the lock immediately with no manual intervention.

**The PID file is informational only.** PID files go stale and PIDs get reused;
using one as the lock is a well-known anti-pattern. Nothing here decides
liveness from it. ``stop`` verifies the lock is held *before* signalling the
recorded PID, so a reused PID is never signalled.

POSIX only. ``fcntl`` does not exist on Windows, and this module fails at import
there rather than offering a degraded mode that would silently permit two
writers.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Final, Self, cast

from amoeba.store import paths

logger = logging.getLogger(__name__)

try:
    import fcntl
except ImportError as error:  # pragma: no cover - POSIX-only by design
    # Explicit failure at import, per the LLD's exclusion of Windows. A
    # degraded mode here would mean two resident processes writing one store.
    raise RuntimeError(
        "amoeba requires POSIX fcntl for single-instance enforcement; "
        f"this platform ({sys.platform}) is not supported"
    ) from error

#: Filenames inside the supervisor directory.
LOCK_FILENAME: Final = "amoeba.lock"
PID_FILENAME: Final = "amoeba.pid"

#: Keys in the PID file. Defined once so the writer and every reader agree.
PID_KEY_PID: Final = "pid"
PID_KEY_STARTED_AT: Final = "started_at"
PID_KEY_VERSION: Final = "version"


def lock_path(env: dict[str, str] | None = None) -> Path:
    """The lock file for this supervisor directory."""
    return paths.store_dir(env) / LOCK_FILENAME


def pid_file_path(env: dict[str, str] | None = None) -> Path:
    """The PID file for this supervisor directory."""
    return paths.store_dir(env) / PID_FILENAME


@dataclass(frozen=True)
class PidFileContents:
    """What a readable PID file said. Informational, never authoritative."""

    pid: int
    started_at: str
    version: str


def write_pid_file(path: Path, *, version: str) -> PidFileContents:
    """Write the informational PID file.

    Written *after* the lock is acquired, so a live process can legitimately
    hold the lock with no PID file yet — a state ``stop`` and ``status`` both
    handle explicitly.
    """
    contents = PidFileContents(
        pid=os.getpid(),
        started_at=datetime.now(UTC).isoformat(),
        version=version,
    )
    path.write_text(
        json.dumps(
            {
                PID_KEY_PID: contents.pid,
                PID_KEY_STARTED_AT: contents.started_at,
                PID_KEY_VERSION: contents.version,
            }
        ),
        encoding="utf-8",
    )
    return contents


def read_pid_file(path: Path) -> PidFileContents | None:
    """Read the PID file, or ``None`` when it is absent, truncated, or corrupt.

    All three failure modes collapse to ``None`` deliberately: the caller's
    decision is the same in each case, and the lock — not this file — is what
    says whether a process is alive.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        # Specific: absent or unreadable. Informational file; nothing to log
        # loudly about, and the lock is what the caller actually trusts.
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Specific: a truncated or hand-edited file. Presents identically to
        # absent, which is a state the lifecycle commands handle explicitly.
        logger.warning("pid file %s is not valid JSON", path)
        return None

    if not isinstance(payload, dict):
        logger.warning("pid file %s does not hold an object", path)
        return None

    # json.loads is typed as returning Any, so the decoded object is narrowed
    # once here rather than at each field read.
    fields = cast("dict[str, object]", payload)
    pid = fields.get(PID_KEY_PID)
    started_at = fields.get(PID_KEY_STARTED_AT)
    version = fields.get(PID_KEY_VERSION)

    if not isinstance(pid, int) or not isinstance(started_at, str):
        logger.warning("pid file %s is missing a required field", path)
        return None

    return PidFileContents(
        pid=pid,
        started_at=started_at,
        version=version if isinstance(version, str) else "unknown",
    )


class InstanceLock:
    """An advisory ``flock`` guaranteeing one resident process per directory.

    Use as a context manager, or call :meth:`acquire` and :meth:`release`
    directly::

        with InstanceLock() as lock:
            if not lock.acquired:
                ...  # another process holds it

    The lock file itself is never deleted to "recover": a stale lock cannot
    exist, because the kernel drops the lock when the holder dies. Deleting it
    would instead break the guarantee, by letting a second process lock a
    different inode with the same name.
    """

    def __init__(self, path: Path | None = None) -> None:
        """Build a lock over ``path``, defaulting to the supervisor directory."""
        self._path = path if path is not None else lock_path()
        self._descriptor: int | None = None

    @property
    def path(self) -> Path:
        """The lock file this instance locks."""
        return self._path

    @property
    def acquired(self) -> bool:
        """Whether this object currently holds the lock."""
        return self._descriptor is not None

    def acquire(self) -> bool:
        """Try to take the lock without blocking.

        Returns:
            ``True`` when the lock is now held by this object, ``False`` when
            another process holds it. Contention is a return value rather than
            an exception, because "already running" is an expected outcome.

        Raises:
            OSError: If the lock file cannot be created or opened at all, which
                is a genuine environment failure rather than contention.
        """
        if self._descriptor is not None:
            return True

        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o644)

        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            # Specific: another process holds the lock. Expected, and reported
            # as False rather than raised, so callers need no try/except for
            # the ordinary "already running" case.
            os.close(descriptor)
            return False

        self._descriptor = descriptor
        return True

    def release(self) -> None:
        """Release the lock and close the descriptor. Safe to call twice.

        The file is deliberately **not** removed: see the class docstring.
        """
        if self._descriptor is None:
            return

        descriptor = self._descriptor
        self._descriptor = None
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    def held_by_another_process(self) -> bool:
        """Whether some *other* process currently holds the lock.

        This is what ``stop`` and ``status`` key on. It works by trying to take
        the lock and immediately dropping it again if that succeeds, so it
        reports on the kernel's view rather than on any file's contents.

        Raises:
            RuntimeError: If called while this object holds the lock, which
                would make the answer meaningless.
        """
        if self._descriptor is not None:
            raise RuntimeError(
                "held_by_another_process() is meaningless while this object "
                "holds the lock"
            )

        try:
            descriptor = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o644)
        except OSError:
            # Specific: the directory does not exist, so nothing can be
            # running against it.
            return False

        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            # Specific: someone else holds it — which is the question asked.
            return True
        else:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            return False
        finally:
            os.close(descriptor)

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
