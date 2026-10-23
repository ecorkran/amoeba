"""Shared helpers for driving the real ``amoeba`` CLI as a subprocess.

Every invocation gets ``AMOEBA_STORE_DIR`` pointed at a directory under
pytest's ``tmp_path``. ``tests/test_cli_safety.py`` checks mechanically that no
CLI test can reach the real supervisor directory or the real Squadron runs
directory, rather than trusting that nobody wrote such a test.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sq_stub import write_sq_stub

from amoeba.serve.settings import TOKEN_ENV_VAR

#: How long to wait for a CLI invocation that is expected to return promptly.
COMMAND_TIMEOUT_SECONDS = 30.0

#: How long to wait for ``start`` to reach a running state.
START_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class CommandResult:
    """What one CLI invocation produced."""

    returncode: int
    stdout: str
    stderr: str


def cli_environment(supervisor_dir: Path) -> dict[str, str]:
    """An environment pointing the CLI at a throwaway supervisor directory.

    Built by copying the real environment and overriding two variables.
    ``AMOEBA_STORE_DIR`` is set so the child can never resolve the real
    supervisor location; the runs directory travels as ``--sq-runs-dir``,
    because the project adds no new environment reads (D3). ``PATH`` gets a stub
    ``sq`` first (below). The serve token is dropped: a real one in the
    developer's shell must never reach a child; a test that needs one sets it
    itself.

    ``start`` probes ``sq`` before its loop (slice 122, D9), and no test runs
    the real ``sq``. So the stub is written to disk by this call (idempotently),
    in ``supervisor_dir.parent``, which must therefore be a throwaway
    directory. Every suite that starts a process gets it; a test that wants no
    ``sq`` replaces ``PATH`` afterwards.
    """
    environment = dict(os.environ)
    environment.pop(TOKEN_ENV_VAR, None)
    environment["AMOEBA_STORE_DIR"] = str(supervisor_dir)
    stub_dir = write_sq_stub(supervisor_dir.parent / "stub-sq-bin")
    environment["PATH"] = f"{stub_dir}{os.pathsep}{environment['PATH']}"
    return environment


def run_cli(
    arguments: list[str],
    supervisor_dir: Path,
    *,
    timeout: float = COMMAND_TIMEOUT_SECONDS,
    environment: dict[str, str] | None = None,
) -> CommandResult:
    """Invoke the real CLI and wait for it to finish.

    ``environment`` replaces :func:`cli_environment`; build it from that
    function so ``AMOEBA_STORE_DIR`` still points at the throwaway directory.
    """
    completed = subprocess.run(
        [sys.executable, "-m", "amoeba.cli.main", *arguments],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=environment if environment is not None else cli_environment(supervisor_dir),
        check=False,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


class BackgroundCli:
    """A long-running CLI invocation, such as ``start``."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process

    @property
    def pid(self) -> int:
        """The subprocess's pid."""
        return self._process.pid

    def is_running(self) -> bool:
        """Whether the invocation is still alive."""
        return self._process.poll() is None

    def wait(self, timeout: float = COMMAND_TIMEOUT_SECONDS) -> int:
        """Wait for exit and return the status."""
        return self._process.wait(timeout=timeout)

    def kill_and_wait(self, timeout: float = COMMAND_TIMEOUT_SECONDS) -> int:
        """SIGKILL the invocation, simulating a crash."""
        self._process.kill()
        return self._process.wait(timeout=timeout)

    def output(self) -> CommandResult:
        """Collect whatever the invocation produced, after it has exited."""
        stdout, stderr = self._process.communicate(timeout=COMMAND_TIMEOUT_SECONDS)
        return CommandResult(
            returncode=self._process.returncode, stdout=stdout, stderr=stderr
        )

    def cleanup(self) -> None:
        """Make sure the invocation is gone, whatever the test did."""
        if self.is_running():
            self._process.kill()
            self._process.wait(timeout=COMMAND_TIMEOUT_SECONDS)


def start_background(
    supervisor_dir: Path,
    extra_arguments: list[str] | None = None,
    environment: dict[str, str] | None = None,
) -> BackgroundCli:
    """Launch ``amoeba start`` in the background. ``environment`` as in run_cli."""
    return BackgroundCli(
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "amoeba.cli.main",
                "start",
                *(extra_arguments or []),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=(
                environment
                if environment is not None
                else cli_environment(supervisor_dir)
            ),
        )
    )


def await_running(supervisor_dir: Path, timeout: float = START_TIMEOUT_SECONDS) -> None:
    """Wait until ``status`` reports the supervisor running."""
    deadline = time.monotonic() + timeout
    last: CommandResult | None = None
    while time.monotonic() < deadline:
        if (supervisor_dir / "amoeba.pid").exists():
            last = run_cli(["status"], supervisor_dir)
            if last.stdout.startswith("running"):
                return
        time.sleep(0.05)
    raise AssertionError(
        f"the supervisor never reported running within {timeout}s; "
        f"last status: {last!r}"
    )


#: A running process applies a submission on its next tick; generous for a
#: loaded machine.
APPLY_TIMEOUT_SECONDS = 20.0


def start_running(supervisor_dir: Path, runs_dir: Path) -> BackgroundCli:
    """``amoeba start`` with a fast tick, returned once it reports running."""
    process = start_background(
        supervisor_dir, ["--sq-runs-dir", str(runs_dir), "--idle-interval", "0.05"]
    )
    await_running(supervisor_dir)
    return process


def stop_running(supervisor_dir: Path, process: BackgroundCli) -> None:
    """``amoeba stop``, asserting a clean exit."""
    assert run_cli(["stop"], supervisor_dir).returncode == 0
    assert process.wait() == 0
    process.cleanup()


def await_condition(
    condition: Callable[[], bool], what: str, timeout: float = APPLY_TIMEOUT_SECONDS
) -> None:
    """Poll until ``condition`` holds, failing with ``what`` on timeout."""
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, f"{what} did not happen"
        time.sleep(0.05)


def submit_cli(supervisor_dir: Path, project_id: str, *arguments: str) -> str:
    """``amoeba submit …`` for a project; returns the printed submission id."""
    result = run_cli(["submit", *arguments, "--project", project_id], supervisor_dir)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def await_stopped(supervisor_dir: Path, timeout: float = START_TIMEOUT_SECONDS) -> None:
    """Wait until ``status`` reports the supervisor stopped."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if run_cli(["status"], supervisor_dir).stdout.startswith("stopped"):
            return
        time.sleep(0.05)
    raise AssertionError(f"the supervisor never reported stopped within {timeout}s")


def start_serve(
    supervisor_dir: Path,
    arguments: list[str],
    environment: dict[str, str] | None = None,
) -> BackgroundCli:
    """Launch ``amoeba serve`` in the background. ``environment`` as in run_cli."""
    return BackgroundCli(
        subprocess.Popen(
            [sys.executable, "-m", "amoeba.cli.main", "serve", *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=(
                environment
                if environment is not None
                else cli_environment(supervisor_dir)
            ),
        )
    )


def free_port() -> int:
    """A loopback port nothing is listening on right now."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def await_listening(
    port: int, process: BackgroundCli, timeout: float = START_TIMEOUT_SECONDS
) -> None:
    """Wait until ``port`` accepts a connection, or fail if ``process`` exits."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not process.is_running():
            raise AssertionError(f"the server exited: {process.output()}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
        except OSError:
            # Specific: not listening yet; poll again until the deadline.
            time.sleep(0.05)
            continue
        return
    raise AssertionError(f"nothing listened on port {port} within {timeout}s")
