"""The run file reader (slice 223, D2): ``params`` and ``execution_mode``.

Squadron prints neither field in ``sq runs wait --json``, so this is the one place
that opens ``~/.config/squadron/runs/<run_id>.json``. It checks ``schema_version``
first (a file of another version need not have the other fields) and never reads
``paused_at`` from the file (the file writes it ``...Z``, the ``wait`` document
``...+00:00``; D1). ``runs_dir`` is an argument, so only the process boundary decides
where the directory is. A problem is a value naming the file and field; the caller
raises, and nothing falls back to a guessed mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError

#: The run file layout this reader understands.
SUPPORTED_SCHEMA_VERSION: Final = 5

RUN_FILE_SUFFIX: Final = ".json"
SCHEMA_VERSION_FIELD: Final = "schema_version"


class ExecutionMode(StrEnum):
    """How Squadron executes a run's steps."""

    SDK = "sdk"
    PROMPT_ONLY = "prompt-only"


@dataclass(frozen=True)
class RunFacts:
    """What the run file says about a run."""

    params: dict[str, str]
    execution_mode: ExecutionMode


@dataclass(frozen=True)
class RunFileProblem:
    """The run file could not be read. ``reason`` names the file and the field."""

    reason: str


class _Header(BaseModel):
    """The one field read before any other, so another version is named as such."""

    model_config = ConfigDict(extra="ignore")

    schema_version: StrictInt


class _Body(BaseModel):
    """The fields of a version-5 run file the reader uses."""

    model_config = ConfigDict(extra="ignore")

    params: dict[StrictStr, StrictStr]
    execution_mode: ExecutionMode


def read_run_facts(runs_dir: Path, run_id: str) -> RunFacts | RunFileProblem:
    """The run's ``params`` and ``execution_mode``, or the problem with its file."""
    path = runs_dir / f"{run_id}{RUN_FILE_SUFFIX}"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Expected: Squadron has no file for this run; the caller decides.
        return RunFileProblem(f"run file {path} does not exist")
    except OSError as error:
        # Expected: the file exists but cannot be read (permissions, a directory).
        return RunFileProblem(f"run file {path} cannot be read: {error}")
    try:
        header = _Header.model_validate_json(text)
        if header.schema_version != SUPPORTED_SCHEMA_VERSION:
            return RunFileProblem(
                f"run file {path}: {SCHEMA_VERSION_FIELD} is "
                f"{header.schema_version}, this reader understands "
                f"{SUPPORTED_SCHEMA_VERSION}"
            )
        body = _Body.model_validate_json(text)
    except ValidationError as error:
        # Expected: not JSON, not an object, or a field missing or of the wrong
        # type or value; named by file and field, never defaulted.
        return RunFileProblem(f"run file {path}: {_problems(error)}")
    return RunFacts(params=body.params, execution_mode=body.execution_mode)


def _problems(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in problem['loc']) or 'document'}: "
        f"{problem['msg']} (got {problem['input']!r})"
        for problem in error.errors()
    )
