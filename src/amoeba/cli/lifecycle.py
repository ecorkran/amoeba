"""``start``, ``stop``, and ``status``.

All three key on the **instance lock**, never on the PID file. The lock is what
the kernel maintains, so it cannot go stale; the PID file is informational and
is only ever consulted *after* the lock has confirmed that something is alive.
That ordering is what makes "a reused PID is never signalled" true rather than
merely likely.

``stop`` never escalates to ``SIGKILL``. If the process will not stop, that is
the operator's decision to make, and crash-only means an external kill is a
correct and recoverable remedy.
"""

from __future__ import annotations

import os
import signal
import sys
import time

from amoeba.cli.main import VERSION, ExitCode
from amoeba.process.host import ResidentProcess
from amoeba.process.instance_lock import (
    InstanceLock,
    PidFileContents,
    lock_path,
    pid_file_path,
    read_pid_file,
)
from amoeba.process.settings import ProcessSettings
from amoeba.store import paths

#: How often ``stop`` re-checks whether the lock has been released.
_LOCK_POLL_INTERVAL_SECONDS = 0.05


def start(settings: ProcessSettings) -> ExitCode:
    """Run the resident process in the foreground until it is stopped.

    Foreground by decision (D1): detaching belongs to whatever launched this.
    Logs go to stderr, and ``stop``/``status`` work identically either way
    because they key on the lock rather than on a parent relationship.

    Raises:
        AlreadyRunningError: Mapped by the boundary handler to
            ``ExitCode.ALREADY_RUNNING``.
        StartupFailedError: Mapped to ``ExitCode.STARTUP_FAILED``.
        GraceExpiredError: Mapped to ``ExitCode.GRACE_EXPIRED``.
    """
    process = ResidentProcess(
        settings,
        store_dir=paths.store_dir(),
        version=VERSION,
        # No tenants: this slice ships none. The process starts, recovers,
        # idles, and stops.
        tenants=(),
        grace_expired_exit_status=int(ExitCode.GRACE_EXPIRED),
        # A tenant that never returns must not hold the process forever; the
        # operator's remedy would otherwise be an external kill.
        exit_on_grace_expiry=True,
    )
    process.install_signal_handlers()
    process.run()
    return ExitCode.OK


def stop(settings: ProcessSettings) -> ExitCode:
    """Ask a running resident process to stop, and wait for it to let go.

    The lock is confirmed held *before* anything is signalled, so a PID that
    has been reused by an unrelated process is never sent a signal.
    """
    lock = InstanceLock(lock_path())

    if not lock.held_by_another_process():
        print("amoeba: not running", file=sys.stderr)
        return ExitCode.NOT_RUNNING

    contents = read_pid_file(pid_file_path())
    if contents is None:
        # The lock is held, so something *is* running — but there is no pid to
        # signal. Guessing one would risk signalling an unrelated process, so
        # this reports and signals nothing. The remedy is the operator's.
        print(
            "amoeba: running, but not addressable: the lock at "
            f"{lock.path} is held and the pid file is absent or unreadable. "
            "Nothing was signalled.",
            file=sys.stderr,
        )
        return ExitCode.NO_STOP_TARGET

    try:
        os.kill(contents.pid, signal.SIGTERM)
    except ProcessLookupError:
        # Specific: the process died between the lock check and the signal.
        # Harmless — the thing stop wanted has already happened.
        print(f"amoeba: process {contents.pid} already gone", file=sys.stderr)
        return ExitCode.OK
    except PermissionError:
        print(
            f"amoeba: not permitted to signal process {contents.pid}",
            file=sys.stderr,
        )
        return ExitCode.FAILURE

    if _await_release(lock, settings.stop_timeout_seconds):
        print(f"amoeba: stopped (pid {contents.pid})", file=sys.stderr)
        return ExitCode.OK

    # Deliberately no SIGKILL escalation: whether to kill is the operator's
    # decision, and crash-only makes it a safe one.
    print(
        f"amoeba: process {contents.pid} did not stop within "
        f"{settings.stop_timeout_seconds}s",
        file=sys.stderr,
    )
    return ExitCode.STOP_TIMEOUT


def _await_release(lock: InstanceLock, timeout_seconds: float) -> bool:
    """Wait for the lock to be released, returning whether it was."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not lock.held_by_another_process():
            return True
        time.sleep(_LOCK_POLL_INTERVAL_SECONDS)
    return not lock.held_by_another_process()


def status() -> ExitCode:
    """Report whether a resident process is running, and what it looks like.

    Four distinct states, because the lock and the PID file can disagree and
    the difference matters to an operator:

    ``running`` (pid and start time)
        The lock is held and the PID file is readable.
    ``running (pid unknown)``
        The lock is held but the PID file is absent or corrupt. ``stop`` will
        report ``NO_STOP_TARGET`` for this state.
    ``stopped (stale pid file)``
        Nothing holds the lock but a PID file remains — exactly what
        ``kill -9`` leaves behind. Harmless.
    ``stopped``
        Nothing holds the lock and there is no PID file.
    """
    lock = InstanceLock(lock_path())
    contents = read_pid_file(pid_file_path())
    running = lock.held_by_another_process()

    if running:
        print(_describe_running(contents))
        return ExitCode.OK

    if contents is not None:
        print("stopped (stale pid file)")
    else:
        print("stopped")
    return ExitCode.NOT_RUNNING_STATUS


def _describe_running(contents: PidFileContents | None) -> str:
    """Render the running line, with or without a usable PID file."""
    if contents is None:
        return "running (pid unknown)"
    return (
        f"running  pid={contents.pid}  since={contents.started_at}  "
        f"version={contents.version}"
    )
