"""A stand-in woken agent for the waking live test (slice 244, D12).

It does what a real woken agent's rules say and nothing more: run ``amoeba inbox``,
accept and then complete each open request it received with ``amoeba reply``, read
``inbox`` once more before it ends, and exit. It spends nothing. It takes its own cost
or time cap, ``--max-seconds``, as the wake-command contract requires, and enforces it.

A wake command gets only the ``WAKE_ENV_NAMES`` variables, so the case's controls are
flags, never environment variables:

* ``--gate-file PATH``: wait until PATH exists before reading ``inbox``.
* ``--sleep-seconds N``: sleep N seconds before reading ``inbox`` (past the timeout).
* ``--parent-pid-file PATH``: write the parent pid, which is the wrapper's, to PATH.
* ``--cf-data-dir PATH``: the Context Forge data directory its ``amoeba`` calls use (a
  throwaway one in the test; a real agent's repo needs no such flag).

It finds ``amoeba`` through ``PATH`` only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Final

AMOEBA_COMMAND: Final = "amoeba"
POLL_SECONDS: Final = 0.1
#: The exit code of an agent that ran out of its own cap.
EXIT_CAP_REACHED: Final = 4
CF_DATA_DIR_VARIABLE: Final = "CONTEXT_FORGE_DATA_DIR"
DONE_TEXT: Final = "done by the fixture agent"


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="a stand-in woken agent")
    parser.add_argument("--max-seconds", type=float, required=True)
    parser.add_argument("--gate-file", type=Path)
    parser.add_argument("--sleep-seconds", type=float)
    parser.add_argument("--parent-pid-file", type=Path)
    parser.add_argument("--cf-data-dir", type=Path)
    return parser.parse_args(argv)


class CapReached(Exception):
    """The agent's own ``--max-seconds`` ran out."""


class Agent:
    def __init__(self, arguments: argparse.Namespace) -> None:
        self._deadline = time.monotonic() + arguments.max_seconds
        self._environment = dict(os.environ)
        if arguments.cf_data_dir is not None:
            self._environment[CF_DATA_DIR_VARIABLE] = str(arguments.cf_data_dir)

    def check_cap(self) -> None:
        if time.monotonic() >= self._deadline:
            raise CapReached

    def wait_for(self, gate: Path) -> None:
        while not gate.exists():
            self.check_cap()
            time.sleep(POLL_SECONDS)

    def sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check_cap()
            time.sleep(POLL_SECONDS)

    def amoeba(self, *arguments: str) -> dict[str, Any]:
        """``amoeba <arguments> -j`` found on ``PATH``; the result document."""
        name, *rest = arguments
        completed = subprocess.run(
            [AMOEBA_COMMAND, name, "-j", *rest],
            env=self._environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=max(1.0, self._deadline - time.monotonic()),
        )
        if completed.returncode != 0:
            sys.stderr.write(completed.stdout + completed.stderr)
            raise SystemExit(completed.returncode)
        document: dict[str, Any] = json.loads(completed.stdout)
        return document

    def open_requests(self) -> list[str]:
        """The ids of the open requests this repo received."""
        inbox = self.amoeba("inbox")
        return [
            request["id"]
            for request in inbox["requests"]
            if request["direction"] == "received" and request["state"] == "open"
        ]

    def handle(self, request_id: str) -> None:
        self.check_cap()
        self.amoeba("reply", request_id, "accept")
        self.amoeba("reply", request_id, "done", "--text", DONE_TEXT)

    def run(self) -> None:
        """Read ``inbox``, handle what is open, and read it again before ending."""
        for _ in range(2):
            for request_id in self.open_requests():
                self.handle(request_id)


def main(argv: list[str]) -> int:
    arguments = _arguments(argv)
    if arguments.parent_pid_file is not None:
        arguments.parent_pid_file.write_text(str(os.getppid()), encoding="utf-8")
    agent = Agent(arguments)
    try:
        if arguments.gate_file is not None:
            agent.wait_for(arguments.gate_file)
        if arguments.sleep_seconds is not None:
            agent.sleep(arguments.sleep_seconds)
        agent.run()
    except (CapReached, subprocess.TimeoutExpired):
        sys.stderr.write("the fixture agent reached its own cap\n")
        return EXIT_CAP_REACHED
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
