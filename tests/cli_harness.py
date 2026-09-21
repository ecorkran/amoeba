"""Shared helpers for driving the real ``amoeba`` CLI as a subprocess.

Every invocation gets ``AMOEBA_STORE_DIR`` pointed at a directory under
pytest's ``tmp_path``. ``tests/test_cli_safety.py`` checks mechanically that no
CLI test can reach the real supervisor directory or the real Squadron runs
directory, rather than trusting that nobody wrote such a test.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

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

    Built by copying the real environment and *overriding* the store directory,
    so the child inherits PATH and the virtualenv but can never resolve the
    real supervisor location. ``AMOEBA_STORE_DIR`` is the only variable set —
    the runs directory travels as ``--sq-runs-dir``, because the project adds
    no new environment reads (D3).
    """
    environment = dict(os.environ)
    environment["AMOEBA_STORE_DIR"] = str(supervisor_dir)
    return environment


def run_cli(
    arguments: list[str],
    supervisor_dir: Path,
    *,
    timeout: float = COMMAND_TIMEOUT_SECONDS,
) -> CommandResult:
    """Invoke the real CLI and wait for it to finish."""
    completed = subprocess.run(
        [sys.executable, "-m", "amoeba.cli.main", *arguments],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=cli_environment(supervisor_dir),
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
    supervisor_dir: Path, extra_arguments: list[str] | None = None
) -> BackgroundCli:
    """Launch ``amoeba start`` in the background."""
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
            env=cli_environment(supervisor_dir),
        )
    )


def await_running(supervisor_dir: Path, timeout: float = START_TIMEOUT_SECONDS) -> None:
    """Wait until ``status`` reports the supervisor running."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if (supervisor_dir / "amoeba.pid").exists():
            result = run_cli(["status"], supervisor_dir)
            if result.stdout.startswith("running"):
                return
        time.sleep(0.05)
    raise AssertionError(f"the supervisor never reported running within {timeout}s")


def await_stopped(supervisor_dir: Path, timeout: float = START_TIMEOUT_SECONDS) -> None:
    """Wait until ``status`` reports the supervisor stopped."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if run_cli(["status"], supervisor_dir).stdout.startswith("stopped"):
            return
        time.sleep(0.05)
    raise AssertionError(f"the supervisor never reported stopped within {timeout}s")
