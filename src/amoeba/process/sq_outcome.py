"""The one reader of a Squadron run's outcome: ``sq runs wait <id> --timeout 0 --json``.

This is the only module that runs ``sq runs wait`` or parses its output.
Recovery, pruning, and later the Runner all call :func:`poll_run`, so Squadron's
internal run-state files are never read by them.

An expected external failure is an answer, never an exception: a missing
``sq``, a timeout, an unexpected exit, or a document that does not parse each
return a :class:`PollFailure` naming what happened. Unexpected exceptions
propagate.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, ConfigDict, ValidationError

#: The Squadron executable, defined once.
SQ_EXECUTABLE: Final = "sq"

#: ``sq runs wait`` with ``--timeout 0`` reports the run's state and returns.
RUNS_WAIT_ARGUMENTS: Final = ("runs", "wait")
RUNS_WAIT_FLAGS: Final = ("--timeout", "0", "--json")

#: How much of stderr a failure reason carries.
STDERR_TAIL_CHARS: Final = 300


class RunOutcome(StrEnum):
    """The eight outcomes ``sq runs wait`` reports; one per exit code."""

    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    #: With ``--timeout 0`` this means the run is still going.
    TIMED_OUT = "timed_out"
    NOT_FOUND = "not_found"
    UNREADABLE = "unreadable"
    UNKNOWN_STATUS = "unknown_status"
    ORPHANED = "orphaned"


#: Squadron's exit code for a rejected command line. It is not a run outcome.
SQ_USAGE_ERROR_EXIT_CODE: Final = 2

#: Squadron's exit code for each outcome. Usage errors are not here.
OUTCOME_EXIT_CODES: Final[Mapping[RunOutcome, int]] = MappingProxyType(
    {
        RunOutcome.COMPLETED: 0,
        RunOutcome.FAILED: 1,
        RunOutcome.PAUSED: 3,
        RunOutcome.TIMED_OUT: 4,
        RunOutcome.NOT_FOUND: 5,
        RunOutcome.UNREADABLE: 6,
        RunOutcome.UNKNOWN_STATUS: 7,
        RunOutcome.ORPHANED: 8,
    }
)

# The one inverse lookup, built from the table above.
_OUTCOME_BY_EXIT_CODE: Final[Mapping[int, RunOutcome]] = MappingProxyType(
    {code: outcome for outcome, code in OUTCOME_EXIT_CODES.items()}
)


class RunCheckpoint(BaseModel):
    """The part of a run's checkpoint that is read today.

    A null ``paused_at`` means unknown.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    paused_at: datetime | None = None


class RunOutcomeDocument(BaseModel):
    """What ``sq runs wait --json`` printed, limited to the fields read.

    Only ``run_id`` and ``outcome`` are always present. A field Squadron did
    not report is ``None`` (unknown) and is never filled in.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    run_id: str
    outcome: RunOutcome
    status: str | None = None
    pipeline: str | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    checkpoint: RunCheckpoint | None = None


@dataclass(frozen=True)
class PollFailure:
    """The outcome could not be read. ``reason`` names the run and the cause."""

    reason: str


type RunPoll = RunOutcomeDocument | PollFailure


def poll_run(run_id: str, *, timeout_seconds: float) -> RunPoll:
    """Ask Squadron for ``run_id``'s outcome once, without waiting.

    Returns:
        The outcome document, or a :class:`PollFailure` when ``sq`` is missing,
        times out, exits unexpectedly, prints something that is not a valid
        document, or prints a document that disagrees with its exit code or
        with the requested id.
    """
    completed = _run_wait(run_id, timeout_seconds)
    if isinstance(completed, PollFailure):
        return completed
    expected = _OUTCOME_BY_EXIT_CODE.get(completed.returncode)
    if expected is None:
        return PollFailure(
            f"`{SQ_EXECUTABLE} runs wait {run_id}` exited {completed.returncode}: "
            f"{completed.stderr.strip()[-STDERR_TAIL_CHARS:]}"
        )
    return _check_document(run_id, expected, completed.stdout)


def _run_wait(
    run_id: str, timeout_seconds: float
) -> subprocess.CompletedProcess[str] | PollFailure:
    command = [SQ_EXECUTABLE, *RUNS_WAIT_ARGUMENTS, run_id, *RUNS_WAIT_FLAGS]
    try:
        return subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        # Expected: `sq` is not on PATH. The caller cannot tell the run's state,
        # so this is an answer for it to act on, not a crash.
        return PollFailure(f"`{SQ_EXECUTABLE}` was not found on PATH (run {run_id})")
    except subprocess.TimeoutExpired:
        # Expected: subprocess.run has killed and reaped `sq`. The state of the
        # run is unknown, and the caller decides what that means.
        return PollFailure(
            f"`{SQ_EXECUTABLE} runs wait {run_id}` did not finish within "
            f"{timeout_seconds} seconds"
        )
    except OSError as error:
        # Expected: `sq` could not be started (permissions, exec format). The
        # run's state is unknown, so report it rather than abort start-up.
        return PollFailure(f"`{SQ_EXECUTABLE}` could not be run for {run_id}: {error}")


def _check_document(run_id: str, expected: RunOutcome, text: str) -> RunPoll:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        # Expected: Squadron printed something that is not JSON.
        return PollFailure(f"`sq runs wait {run_id}` did not print JSON: {error}")
    try:
        document = RunOutcomeDocument.model_validate(raw)
    except ValidationError as error:
        # Expected: JSON that is not a valid outcome document.
        return PollFailure(
            f"`sq runs wait {run_id}` printed an invalid document: {error}"
        )
    if document.outcome is not expected:
        return PollFailure(
            f"`sq runs wait {run_id}` exit code means {expected.value} "
            f"but the document says {document.outcome.value}"
        )
    if document.run_id != run_id:
        return PollFailure(
            f"`sq runs wait {run_id}` answered for run {document.run_id}"
        )
    return document
