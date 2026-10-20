"""One subprocess of the proof, with everything it wrote captured.

Stdout is pumped line by line on a thread so a predicate can poll it without
ever blocking; stderr goes to a file, so a chatty process can never fill a pipe
and stall. ``host_harness.HostProcess`` is the handle for signalling and waiting.
"""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path

from host_harness import READY_MARKER, HostProcess


class LaunchedProcess:
    """A started subprocess and its captured output."""

    def __init__(
        self,
        label: str,
        command: Sequence[str],
        *,
        environment: Mapping[str, str],
        working_dir: Path,
        stderr_path: Path,
    ) -> None:
        self.label = label
        self.stdout_lines: list[str] = []
        self._stderr_path = stderr_path
        self._stderr_handle = stderr_path.open("w", encoding="utf-8")
        process = subprocess.Popen(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=self._stderr_handle,
            text=True,
            env=dict(environment),
            cwd=working_dir,
        )
        self.host = HostProcess(process)
        threading.Thread(target=self._pump, args=(process,), daemon=True).start()

    def _pump(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            self.stdout_lines.append(line.rstrip("\n"))

    @property
    def is_ready(self) -> bool:
        return READY_MARKER in self.stdout_lines

    def captured(self) -> str:
        """Everything this process has written to stdout and stderr so far."""
        self._stderr_handle.flush()
        return (
            f"--- {self.label} stdout ---\n"
            + "\n".join(self.stdout_lines)
            + f"\n--- {self.label} stderr ---\n"
            + self._stderr_path.read_text(encoding="utf-8")
        )

    def close(self) -> None:
        self.host.cleanup()
        self._stderr_handle.close()
