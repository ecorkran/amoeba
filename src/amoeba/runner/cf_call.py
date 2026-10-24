"""The one place the Runner runs ``cf``: a bounded call that never raises for the
two failures an external command is expected to have.

A timeout and a missing or unrunnable executable come back as a
:class:`CfCallFailed` answer, not an exception. Everything else the caller sees is
the completed process, stdout and stderr both: CF prints some error documents on
stderr, so a caller classifying a non-zero exit needs both streams.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

#: How much of a command's output a failure message quotes.
OUTPUT_HEAD_CHARS: Final = 200  # keeps a failing call's detail one line long

#: Runs ``cf``: ``subprocess.run`` in production, a fake in unit tests.
type CfRun = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class CfCallFailed:
    """The command could not be run to completion; ``detail`` names it and why."""

    detail: str


def output_head(completed: subprocess.CompletedProcess[str]) -> str:
    """The start of whichever stream carried output, for a failure detail.

    CF prints some errors on stderr with an empty stdout, so both are tried.
    """
    return (completed.stdout or completed.stderr)[:OUTPUT_HEAD_CHARS]


def run_cf(
    argv: Sequence[str], run: CfRun, timeout_seconds: float
) -> subprocess.CompletedProcess[str] | CfCallFailed:
    """Run one ``cf`` command with a timeout and both output streams captured."""
    shown = " ".join(argv)
    try:
        return run(
            list(argv),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CfCallFailed(f"`{shown}` timed out after {timeout_seconds}s")
    except OSError as error:
        # An expected external failure: cf missing or not runnable.
        return CfCallFailed(f"`{shown}` could not run: {error}")
