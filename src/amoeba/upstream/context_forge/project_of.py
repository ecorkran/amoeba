"""Which Context Forge project a directory (or a name) belongs to.

``cf get --json`` run in a directory prints that directory's project, and with
``-p <id or name>`` a named one. Worktrees and subdirectories of one checkout give
the same project ``id`` because Context Forge says so; nothing here adds worktree
logic. Outside any project Context Forge prints an error document with the code
``PROJECT_NOT_FOUND``, on stderr in the cases recorded in
``tests/fixtures/context_forge``, so both streams are read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final, cast

from amoeba.upstream.context_forge.cli_call import (
    OUTPUT_HEAD_CHARS,
    CfCallFailed,
    CfRun,
    run_cf,
)
from amoeba.upstream.context_forge.target_read import (
    CF_EXECUTABLE,
    CF_JSON_FLAG,
    CF_PROJECT_FLAG,
)

CF_GET_COMMAND: Final = "get"
#: ``cf get`` reads local files; a call that takes this long is stuck.
CF_GET_TIMEOUT_SECONDS: Final = 30.0

_NOT_FOUND_CODE: Final = "PROJECT_NOT_FOUND"
_CODE_KEY: Final = "code"
_MESSAGE_KEY: Final = "message"
_ID_KEY: Final = "id"
_NAME_KEY: Final = "name"
_PROJECT_PATH_KEY: Final = "projectPath"


@dataclass(frozen=True)
class CFProject:
    """The Context Forge project a lookup found; other fields are ignored."""

    id: str
    name: str
    project_path: str


@dataclass(frozen=True)
class CFProjectNotFound:
    """No project there; ``message`` is Context Forge's own text."""

    message: str


def _json_object(text: str) -> dict[str, object] | None:
    """``text`` parsed as a JSON object, or ``None`` if it is anything else."""
    try:
        document: object = json.loads(text)
    except json.JSONDecodeError:
        # Expected: a stream that holds no JSON (usually the empty one).
        return None
    if not isinstance(document, dict):
        return None
    # json.loads of an object always has string keys.
    return cast("dict[str, object]", document)


def _not_found(streams: tuple[str, ...]) -> CFProjectNotFound | None:
    for stream in streams:
        document = _json_object(stream)
        if document is not None and document.get(_CODE_KEY) == _NOT_FOUND_CODE:
            message = document.get(_MESSAGE_KEY)
            return CFProjectNotFound(message if isinstance(message, str) else "")
    return None


def _project(stdout: str) -> CFProject | None:
    document = _json_object(stdout)
    if document is None:
        return None
    fields = [document.get(key) for key in (_ID_KEY, _NAME_KEY, _PROJECT_PATH_KEY)]
    if not all(isinstance(field, str) and field for field in fields):
        return None
    project_id, name, project_path = (str(field) for field in fields)
    return CFProject(id=project_id, name=name, project_path=project_path)


def project_of(
    *, directory: Path | None = None, reference: str | None = None, run: CfRun
) -> CFProject | CFProjectNotFound | CfCallFailed:
    """The project of ``directory``, or the one named by ``reference``.

    Exactly one of the two is given. ``CfCallFailed`` means Context Forge did not
    give a usable answer, which is not the same as "not a project".
    """
    if (directory is None) == (reference is None):
        raise ValueError("give exactly one of directory and reference")
    argv = [CF_EXECUTABLE, CF_GET_COMMAND, CF_JSON_FLAG]
    if reference is not None:
        argv += [CF_PROJECT_FLAG, reference]
    caller = run if directory is None else partial(run, cwd=directory)
    completed = run_cf(argv, caller, CF_GET_TIMEOUT_SECONDS)
    if isinstance(completed, CfCallFailed):
        return completed
    missing = _not_found((completed.stdout, completed.stderr))
    if missing is not None:
        return missing
    shown = " ".join(argv)
    head = (completed.stdout or completed.stderr)[:OUTPUT_HEAD_CHARS]
    if completed.returncode != 0:
        return CfCallFailed(f"`{shown}` exited {completed.returncode}: {head}")
    project = _project(completed.stdout)
    if project is None:
        return CfCallFailed(f"`{shown}` gave no project document: {head}")
    return project
