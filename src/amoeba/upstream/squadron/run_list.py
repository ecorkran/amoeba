"""The one reader of ``sq runs list --json`` (slice 224, D1).

It is the only module that runs ``sq runs list`` or parses its output. Called with
``--all`` (228 D4): the default listing holds every running, paused and failed run but
only some completed ones, so a run absent from it could still exist; ``--all`` adds
every completed run, so a run absent from it is unknown to ``sq`` unless its run
file says otherwise (``run_file_exists``).
Only stdout is parsed: ``sq`` may print a warning on stderr (for example that some runs
reference unavailable pipelines), and that is not an error.

Each checkpoint is read through ``poll_run``'s checkpoint model, so ``paused_at`` is the
text 223 stores, and only ``kind``, ``paused_at`` and ``question`` are kept. A status
``sq`` newer than this code reports stays a raw string. An expected failure is a
:class:`RunListProblem` quoting the output head, never an exception.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, StrictStr, TypeAdapter, ValidationError

from amoeba.upstream.context_forge.cli_call import OUTPUT_HEAD_CHARS, output_head
from amoeba.upstream.squadron.run_outcome import SQ_EXECUTABLE, RunCheckpoint

#: ``sq runs list --json``.
RUNS_LIST_ARGUMENTS: Final = ("runs", "list")
RUNS_LIST_FLAGS: Final = ("--json", "--all")

#: The listing's status for a paused run.
PAUSED_STATUS: Final = "paused"
#: The listing's status for a finished run.
COMPLETED_STATUS: Final = "completed"


@dataclass(frozen=True)
class ListedCheckpoint:
    """The parts of a checkpoint ``status`` uses. ``kind`` is raw text."""

    kind: str | None
    #: ``paused_at`` as ``sq runs wait --json`` prints it (the form 223 stores).
    paused_at: str | None
    question: str | None


@dataclass(frozen=True)
class ListedRun:
    """One run of the listing."""

    run_id: str
    pipeline: str
    #: Squadron's status text; kept raw so a status this code has no name for is shown.
    status: str
    #: Where the run was started; ``None`` for a run from before ``sq`` 0.24.24.
    working_directory: Path | None
    checkpoint: ListedCheckpoint | None

    @property
    def is_paused(self) -> bool:
        return self.status == PAUSED_STATUS

    @property
    def is_completed(self) -> bool:
        return self.status == COMPLETED_STATUS


@dataclass(frozen=True)
class RunListProblem:
    """The listing could not be read; ``reason`` names the command and the cause."""

    reason: str


class _Entry(BaseModel):
    """One element of the listing. Every key is required (``None`` is a value for
    ``working_directory`` and ``checkpoint``, not an absence); others are ignored."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    run_id: StrictStr
    pipeline: StrictStr
    status: StrictStr
    working_directory: StrictStr | None
    checkpoint: RunCheckpoint | None


_ENTRIES: Final = TypeAdapter(list[_Entry])


def _command_text() -> str:
    return " ".join([SQ_EXECUTABLE, *RUNS_LIST_ARGUMENTS, *RUNS_LIST_FLAGS])


def list_runs(*, timeout_seconds: float) -> list[ListedRun] | RunListProblem:
    """Every run ``sq runs list --json`` reports, or the problem reading it."""
    command = [SQ_EXECUTABLE, *RUNS_LIST_ARGUMENTS, *RUNS_LIST_FLAGS]
    shown = _command_text()
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        # Expected: `sq` is not on PATH; the caller reports it.
        return RunListProblem(f"`{SQ_EXECUTABLE}` was not found on PATH")
    except subprocess.TimeoutExpired:
        # Expected: subprocess.run has killed and reaped `sq`; the state is unknown.
        return RunListProblem(f"`{shown}` did not finish within {timeout_seconds} s")
    except OSError as error:
        # Expected: `sq` could not be started (permissions, exec format).
        return RunListProblem(f"`{SQ_EXECUTABLE}` could not be run: {error}")
    head = output_head(completed)
    if completed.returncode != 0:
        return RunListProblem(f"`{shown}` exited {completed.returncode}: {head}")
    return parse_listing(completed.stdout)


def parse_listing(stdout: str) -> list[ListedRun] | RunListProblem:
    """The runs of ``sq runs list --json``'s stdout, or the problem with it."""
    shown = _command_text()
    head = stdout[:OUTPUT_HEAD_CHARS]
    try:
        document: object = json.loads(stdout)
    except json.JSONDecodeError:
        # Expected: sq printed something that is not JSON.
        return RunListProblem(f"`{shown}` did not print JSON: {head!r}")
    try:
        entries = _ENTRIES.validate_python(document)
    except ValidationError as error:
        # Expected: JSON that is not a list of runs with the fields read.
        return RunListProblem(f"`{shown}` printed an unexpected document: {error}")
    return [_listed(entry) for entry in entries]


def _listed(entry: _Entry) -> ListedRun:
    checkpoint = entry.checkpoint
    return ListedRun(
        run_id=entry.run_id,
        pipeline=entry.pipeline,
        status=entry.status,
        working_directory=(
            None if entry.working_directory is None else Path(entry.working_directory)
        ),
        checkpoint=(
            None
            if checkpoint is None
            else ListedCheckpoint(
                kind=checkpoint.kind,
                paused_at=checkpoint.paused_at_text,
                question=checkpoint.question,
            )
        ),
    )
