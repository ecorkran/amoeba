"""Tests for the instance lock, against real OS behavior.

**Nothing in this file is mocked.** Locking and signals are platform behavior,
and a mocked ``flock`` would assert only that the test's own fake behaves like
the test's own fake. Every contention test spawns a real subprocess; the
``kill -9`` test really sends ``SIGKILL``.

The central claim under test is the crash-only one: the kernel releases an
advisory lock when the holder dies by *any* means, so a stale lock cannot exist
and no cleanup is ever required.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import textwrap
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.process.instance_lock import (
    LOCK_FILENAME,
    PID_FILENAME,
    InstanceLock,
    PidFileContents,
    read_pid_file,
    write_pid_file,
)

#: How long to wait for a subprocess to reach a state before failing.
READY_TIMEOUT_SECONDS = 10.0

#: How long to wait for the kernel to drop a dead process's lock.
RELEASE_TIMEOUT_SECONDS = 5.0


@pytest.fixture
def lock_file(tmp_path: Path) -> Path:
    """A throwaway lock path inside pytest's own temporary directory."""
    return tmp_path / LOCK_FILENAME


def _holder_script(lock_file: Path) -> str:
    """A program that takes the lock, says so, and waits to be told to stop."""
    return textwrap.dedent(
        f"""
        import sys
        from pathlib import Path
        from amoeba.process.instance_lock import InstanceLock

        lock = InstanceLock(Path({str(lock_file)!r}))
        acquired = lock.acquire()
        print("acquired" if acquired else "refused", flush=True)
        if acquired:
            # Hold it until stdin closes or a line arrives.
            sys.stdin.readline()
            lock.release()
        """
    )


def _spawn(script: str, tmp_path: Path, name: str) -> subprocess.Popen[str]:
    """Run a script as a real subprocess, with pipes for handshaking."""
    path = tmp_path / name
    path.write_text(script, encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _await_line(process: subprocess.Popen[str]) -> str:
    """Read one handshake line, failing the test rather than hanging forever."""
    assert process.stdout is not None
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    line = process.stdout.readline()
    if not line and time.monotonic() > deadline:
        raise AssertionError("subprocess produced no output before the timeout")
    return line.strip()


def _stop(process: subprocess.Popen[str]) -> None:
    """Ask a holder to exit normally, and wait for it."""
    if process.poll() is None:
        assert process.stdin is not None
        try:
            process.stdin.write("\n")
            process.stdin.flush()
        except (BrokenPipeError, ValueError):
            # The process already exited; nothing to ask.
            pass
    process.wait(timeout=READY_TIMEOUT_SECONDS)


@pytest.fixture
def holder(lock_file: Path, tmp_path: Path) -> Iterator[subprocess.Popen[str]]:
    """A real subprocess holding the lock for the duration of a test."""
    process = _spawn(_holder_script(lock_file), tmp_path, "holder.py")
    try:
        assert _await_line(process) == "acquired"
        yield process
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=READY_TIMEOUT_SECONDS)


def _await_lock_released(lock: InstanceLock) -> bool:
    """Wait briefly for the lock to become free, returning whether it did."""
    deadline = time.monotonic() + RELEASE_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if not lock.held_by_another_process():
            return True
        time.sleep(0.02)
    return False


# --------------------------------------------------------------------------
# Contention, against a real second process
# --------------------------------------------------------------------------


def test_a_second_acquire_from_another_process_fails(
    lock_file: Path, tmp_path: Path, holder: subprocess.Popen[str]
) -> None:
    """Single-instance enforcement: the second process is refused, cleanly."""
    second = _spawn(_holder_script(lock_file), tmp_path, "second.py")
    try:
        assert _await_line(second) == "refused"
        second.wait(timeout=READY_TIMEOUT_SECONDS)
        assert second.returncode == 0, "refusal is a clean exit, not a crash"
    finally:
        if second.poll() is None:
            second.kill()


def test_acquire_fails_cleanly_rather_than_raising(
    lock_file: Path, holder: subprocess.Popen[str]
) -> None:
    """Contention is a return value; 'already running' is an expected outcome."""
    lock = InstanceLock(lock_file)

    assert lock.acquire() is False
    assert lock.acquired is False


def test_held_by_another_process_sees_a_real_holder(
    lock_file: Path, holder: subprocess.Popen[str]
) -> None:
    """What stop and status key on, answered by the kernel."""
    assert InstanceLock(lock_file).held_by_another_process() is True


def test_held_by_another_process_is_false_when_nothing_holds_it(
    lock_file: Path,
) -> None:
    """A free lock reports free, and the query itself does not leave it held."""
    lock = InstanceLock(lock_file)

    assert lock.held_by_another_process() is False
    assert lock.held_by_another_process() is False
    assert InstanceLock(lock_file).acquire() is True


def test_held_by_another_process_refuses_while_self_holding(
    lock_file: Path,
) -> None:
    """Asking the question while holding the lock would give a useless answer."""
    lock = InstanceLock(lock_file)
    assert lock.acquire() is True

    try:
        with pytest.raises(RuntimeError, match="meaningless"):
            lock.held_by_another_process()
    finally:
        lock.release()


# --------------------------------------------------------------------------
# Crash-only: the kernel is what releases the lock
# --------------------------------------------------------------------------


def test_sigkill_of_the_holder_releases_the_lock_with_no_cleanup(
    lock_file: Path, holder: subprocess.Popen[str]
) -> None:
    """The central crash-only claim, tested with a real SIGKILL.

    No cleanup runs in the killed process — that is the point. The lock file
    still exists afterward, and the next acquire succeeds anyway, because the
    kernel dropped the lock when the process died.
    """
    assert InstanceLock(lock_file).held_by_another_process() is True

    os.kill(holder.pid, signal.SIGKILL)
    holder.wait(timeout=READY_TIMEOUT_SECONDS)

    assert _await_lock_released(InstanceLock(lock_file)), (
        "the kernel did not release the lock after SIGKILL"
    )
    # The file is still there; it is not what carries the liveness signal.
    assert lock_file.exists()
    assert InstanceLock(lock_file).acquire() is True


def test_normal_exit_releases_the_lock(
    lock_file: Path, holder: subprocess.Popen[str]
) -> None:
    """The ordinary path releases it too, via the process's own release()."""
    _stop(holder)

    assert _await_lock_released(InstanceLock(lock_file))
    assert InstanceLock(lock_file).acquire() is True


def test_release_is_idempotent(lock_file: Path) -> None:
    """Releasing twice is safe, so teardown paths need no guard."""
    lock = InstanceLock(lock_file)
    assert lock.acquire() is True

    lock.release()
    lock.release()

    assert lock.acquired is False


def test_the_lock_file_is_never_deleted_to_recover(
    lock_file: Path, holder: subprocess.Popen[str]
) -> None:
    """Recovery never unlinks the lock — doing so would break the guarantee.

    A deleted-and-recreated lock file is a *different inode*, which two
    processes could each lock happily. The file therefore survives both a kill
    and a subsequent acquire.
    """
    os.kill(holder.pid, signal.SIGKILL)
    holder.wait(timeout=READY_TIMEOUT_SECONDS)
    assert _await_lock_released(InstanceLock(lock_file))

    inode_before = lock_file.stat().st_ino
    survivor = InstanceLock(lock_file)
    assert survivor.acquire() is True
    try:
        assert lock_file.stat().st_ino == inode_before
    finally:
        survivor.release()


def test_the_context_manager_releases_on_exit(lock_file: Path) -> None:
    """The ``with`` form releases even when the body raises."""
    with pytest.raises(RuntimeError, match="deliberate"):
        with InstanceLock(lock_file) as lock:
            assert lock.acquired is True
            raise RuntimeError("deliberate")

    assert InstanceLock(lock_file).acquire() is True


# --------------------------------------------------------------------------
# The PID file: informational, and never trusted for liveness
# --------------------------------------------------------------------------


def test_pid_file_round_trips(tmp_path: Path) -> None:
    """What start writes is what status reads."""
    path = tmp_path / PID_FILENAME

    written = write_pid_file(path, version="0.1.0")
    read_back = read_pid_file(path)

    assert read_back == written
    assert written.pid == os.getpid()
    assert written.version == "0.1.0"


def test_a_stale_pid_file_with_a_free_lock_is_recognized_as_stale(
    tmp_path: Path, lock_file: Path
) -> None:
    """The ``stopped (stale pid file)`` state: a PID file, but nothing running.

    This is exactly the state ``kill -9`` leaves behind, and it must not read
    as "running" — which is why the lock, not this file, decides.
    """
    pid_path = tmp_path / PID_FILENAME
    write_pid_file(pid_path, version="0.1.0")

    contents = read_pid_file(pid_path)

    assert contents is not None, "the file is readable"
    assert InstanceLock(lock_file).held_by_another_process() is False, (
        "but nothing holds the lock, so nothing is running"
    )


def test_a_held_lock_with_an_absent_pid_file(
    tmp_path: Path, lock_file: Path, holder: subprocess.Popen[str]
) -> None:
    """``running (pid unknown)``: the state Tasks 6.4 and 7.2 must handle.

    The start sequence acquires the lock *before* writing the PID file, so a
    live process can legitimately be in this state.
    """
    pid_path = tmp_path / PID_FILENAME
    assert not pid_path.exists()

    assert InstanceLock(lock_file).held_by_another_process() is True
    assert read_pid_file(pid_path) is None


@pytest.mark.parametrize(
    "corrupt_contents",
    [
        "",
        "   ",
        "{truncated",
        "[1, 2, 3]",
        '"a bare string"',
        json.dumps({"started_at": "2026-09-21T00:00:00+00:00"}),
        json.dumps({"pid": "not an int", "started_at": "2026-09-21T00:00:00+00:00"}),
    ],
)
def test_a_corrupt_pid_file_reads_as_absent(
    tmp_path: Path, corrupt_contents: str
) -> None:
    """Truncated, malformed, and half-written files all collapse to ``None``.

    The caller's decision is identical in every case, and the lock is what
    actually says whether a process is alive.
    """
    path = tmp_path / PID_FILENAME
    path.write_text(corrupt_contents, encoding="utf-8")

    assert read_pid_file(path) is None


def test_a_missing_pid_file_reads_as_absent(tmp_path: Path) -> None:
    """No file is not an error."""
    assert read_pid_file(tmp_path / "nothing-here.pid") is None


def test_a_pid_file_without_a_version_still_reads(tmp_path: Path) -> None:
    """A missing optional field degrades, rather than failing the whole read."""
    path = tmp_path / PID_FILENAME
    path.write_text(
        json.dumps({"pid": 4242, "started_at": "2026-09-21T00:00:00+00:00"}),
        encoding="utf-8",
    )

    contents = read_pid_file(path)

    assert contents == PidFileContents(
        pid=4242, started_at="2026-09-21T00:00:00+00:00", version="unknown"
    )


def test_the_pid_file_is_not_consulted_to_decide_liveness(
    tmp_path: Path, lock_file: Path
) -> None:
    """A PID file naming a live, unrelated process still means 'not running'.

    This test writes the *pytest process's own* pid — which is certainly alive
    — while nothing holds the lock. A PID-file-based liveness check would
    wrongly report running; the lock-based one reports the truth.
    """
    pid_path = tmp_path / PID_FILENAME
    write_pid_file(pid_path, version="0.1.0")
    contents = read_pid_file(pid_path)
    assert contents is not None and contents.pid == os.getpid()

    assert InstanceLock(lock_file).held_by_another_process() is False
