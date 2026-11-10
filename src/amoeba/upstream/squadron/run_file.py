"""The run file reader (slice 223, D2): ``params`` and ``execution_mode``.

Squadron prints neither field in ``sq runs wait --json``, so this is the one place
that opens ``~/.config/squadron/runs/<run_id>.json``. It checks ``schema_version``
and never reads ``paused_at`` from the file (the file writes it ``...Z``, the
``wait`` document ``...+00:00``; D1). ``runs_dir`` is an argument, so only the
process boundary decides where the directory is. A problem is a value naming the
file and field; the caller raises, and nothing falls back to a guessed mode.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, cast

#: The run file layout this reader understands.
SUPPORTED_SCHEMA_VERSION: Final = 5

RUN_FILE_SUFFIX: Final = ".json"
SCHEMA_VERSION_FIELD: Final = "schema_version"
PARAMS_FIELD: Final = "params"
EXECUTION_MODE_FIELD: Final = "execution_mode"


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
        document: object = json.loads(text)
    except json.JSONDecodeError as error:
        # Expected: the file is not JSON, e.g. half-written.
        return RunFileProblem(f"run file {path} is not valid JSON: {error}")
    return _facts(path, document)


def _facts(path: Path, document: object) -> RunFacts | RunFileProblem:
    if not isinstance(document, dict):
        return RunFileProblem(f"run file {path} is not a JSON object")
    fields = cast("dict[str, object]", document)
    version = fields.get(SCHEMA_VERSION_FIELD)
    if version != SUPPORTED_SCHEMA_VERSION or isinstance(version, bool):
        return RunFileProblem(
            f"run file {path}: {SCHEMA_VERSION_FIELD} is {version!r}, "
            f"this reader understands {SUPPORTED_SCHEMA_VERSION}"
        )
    params = _params(path, fields.get(PARAMS_FIELD))
    if isinstance(params, RunFileProblem):
        return params
    mode = _mode(path, fields.get(EXECUTION_MODE_FIELD))
    if isinstance(mode, RunFileProblem):
        return mode
    return RunFacts(params=params, execution_mode=mode)


def _params(path: Path, value: object) -> dict[str, str] | RunFileProblem:
    if not isinstance(value, dict):
        return RunFileProblem(
            f"run file {path}: {PARAMS_FIELD} is missing or not an object"
        )
    params: dict[str, str] = {}
    for key, item in value.items():  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(key, str) or not isinstance(item, str):
            return RunFileProblem(
                f"run file {path}: {PARAMS_FIELD} holds a non-string entry {key!r}"
            )
        params[key] = item
    return params


def _mode(path: Path, value: object) -> ExecutionMode | RunFileProblem:
    if value is None:
        return RunFileProblem(f"run file {path}: {EXECUTION_MODE_FIELD} is missing")
    try:
        return ExecutionMode(value)
    except ValueError:
        # Specific: a mode newer than this code; reported, never mapped to a near one.
        return RunFileProblem(
            f"run file {path}: {EXECUTION_MODE_FIELD} {value!r} is not one of "
            f"{[mode.value for mode in ExecutionMode]}"
        )
