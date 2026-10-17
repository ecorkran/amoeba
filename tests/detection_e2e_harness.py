"""End-to-end harness for slice 106: the real CLI, a fake ``sq``, a follower.

Every command runs as a subprocess against a throwaway supervisor directory
with a fake ``sq`` first on ``PATH``, so the start-up label is known. Helpers
hold no detection assertions.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from cli_harness import (
    APPLY_TIMEOUT_SECONDS,
    COMMAND_TIMEOUT_SECONDS,
    BackgroundCli,
    CommandResult,
    await_running,
    cli_environment,
    run_cli,
    start_background,
)

REPO_ROOT = Path(__file__).parents[1]
DEMO_SCRIPT = REPO_ROOT / "scripts" / "demo_detection.py"
FIXTURES = Path(__file__).parent / "fixtures" / "sq_reviews"
FAKE_SQ_LABEL = "sq-e2e 0.0.0"

#: Fast enough that a test waits seconds, not minutes.
FAST_FLAGS = ("--idle-interval", "0.05", "--review-scan-interval", "0.1")

type ChangeLine = dict[str, object]


class Follower:
    """``amoeba feed --follow`` in the background, its lines collected."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process
        self._lines: list[ChangeLine] = []
        self._guard = threading.Lock()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self._process.stdout is not None
        for line in self._process.stdout:
            with self._guard:
                self._lines.append(json.loads(line))

    @property
    def lines(self) -> list[ChangeLine]:
        with self._guard:
            return list(self._lines)

    @property
    def last_seq(self) -> int:
        lines = self.lines
        return int(str(lines[-1]["seq"])) if lines else 0

    def wait_for(
        self,
        predicate: Callable[[list[ChangeLine]], bool],
        timeout: float = APPLY_TIMEOUT_SECONDS,
    ) -> list[ChangeLine]:
        """Wait until ``predicate(lines)`` holds; fail showing the lines so far."""
        deadline = time.monotonic() + timeout
        while not predicate(lines := self.lines):
            if time.monotonic() > deadline:
                raise AssertionError(
                    "follower never satisfied the condition; lines so far:\n"
                    + "\n".join(json.dumps(line) for line in lines)
                )
            time.sleep(0.05)
        return lines

    def terminate(self) -> int:
        self._process.terminate()
        return self._process.wait(timeout=COMMAND_TIMEOUT_SECONDS)

    def kill(self) -> None:
        if self._process.poll() is None:
            self._process.kill()
        self._process.wait(timeout=COMMAND_TIMEOUT_SECONDS)


class DetectionE2E:
    """One throwaway supervisor directory and the processes run against it."""

    def __init__(self, supervisor_dir: Path, work_dir: Path) -> None:
        self.supervisor_dir = supervisor_dir
        self.runs_dir = work_dir / "runs"
        self.runs_dir.mkdir()
        fake_bin = work_dir / "fake-bin"
        fake_bin.mkdir()
        sq = fake_bin / "sq"
        sq.write_text(f'#!/bin/sh\necho "{FAKE_SQ_LABEL}"\n')
        sq.chmod(0o755)
        self.environment = cli_environment(supervisor_dir)
        self.environment["PATH"] = f"{fake_bin}:{self.environment['PATH']}"
        self._cleanups: list[Callable[[], None]] = []

    def run(self, *arguments: str) -> CommandResult:
        return run_cli(
            list(arguments), self.supervisor_dir, environment=self.environment
        )

    def start_process(self, *extra_flags: str) -> BackgroundCli:
        process = start_background(
            self.supervisor_dir,
            ["--sq-runs-dir", str(self.runs_dir), *FAST_FLAGS, *extra_flags],
            environment=self.environment,
        )
        self._cleanups.append(process.cleanup)
        await_running(self.supervisor_dir)
        return process

    def stop_process(self, process: BackgroundCli) -> None:
        result = self.run("stop")
        assert result.returncode == 0, result.stderr
        assert process.wait() == 0
        process.cleanup()

    def seed_demo(self) -> tuple[str, str]:
        """Run ``scripts/demo_detection.py``; return (slice node, blocked node)."""
        completed = subprocess.run(
            [sys.executable, str(DEMO_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            env=self.environment,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        slice_node, blocked_node = completed.stdout.split()
        return slice_node, blocked_node

    def start_follower(self, project: str, after: int | None = None) -> Follower:
        arguments = ["feed", "--follow", "--project", project]
        if after is not None:
            arguments += ["--after", str(after)]
        follower = Follower(
            subprocess.Popen(
                [sys.executable, "-m", "amoeba.cli.main", *arguments],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                env=self.environment,
            )
        )
        self._cleanups.append(follower.kill)
        return follower

    def inspect_json(
        self, listing: str, project: str, *arguments: str
    ) -> list[ChangeLine]:
        result = self.run(
            "inspect", listing, "--project", project, "--json", *arguments
        )
        assert result.returncode == 0, result.stderr
        rows: list[ChangeLine] = json.loads(result.stdout)
        return rows

    def await_rows(
        self,
        listing: str,
        project: str,
        predicate: Callable[[list[ChangeLine]], bool],
        *arguments: str,
    ) -> list[ChangeLine]:
        """Poll a listing until ``predicate(rows)`` holds."""
        deadline = time.monotonic() + APPLY_TIMEOUT_SECONDS
        while not predicate(rows := self.inspect_json(listing, project, *arguments)):
            if time.monotonic() > deadline:
                raise AssertionError(f"{listing} never matched; rows: {rows}")
            time.sleep(0.1)
        return rows

    def create_project(self, project: str) -> None:
        """Submit ``create-project`` to a running process and wait for its store."""
        result = self.run(
            "submit", "create-project", "--project", project, "--by", "pm"
        )
        assert result.returncode == 0, result.stderr
        deadline = time.monotonic() + APPLY_TIMEOUT_SECONDS
        while project not in self.run("inspect", "projects").stdout:
            assert time.monotonic() < deadline, f"project {project} never appeared"
            time.sleep(0.1)

    def cleanup(self) -> None:
        for cleanup in reversed(self._cleanups):
            cleanup()


def copy_fixture(name: str, directory: Path) -> Path:
    """Copy a real review fixture into ``directory``."""
    return Path(shutil.copy(FIXTURES / name, directory / name))
