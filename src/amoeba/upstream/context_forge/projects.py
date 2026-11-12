"""Context Forge's project names (slice 224, D6): ``cf list projects --json``.

Members are stored by project id only; a name is read when a result is shown and
never stored. Only ``id`` and ``name`` are read: ``projectPath`` is missing on some
entries and ``fileSlice`` and ``isActive`` are not wanted.
"""

from __future__ import annotations

import json
from typing import Final

from amoeba.upstream.context_forge.cli_call import (
    OUTPUT_HEAD_CHARS,
    CfCallFailed,
    CfRun,
    output_head,
    run_cf,
)
from amoeba.upstream.context_forge.target_read import (
    CF_EXECUTABLE,
    list_projects_command,
)

#: ``cf list projects`` reads the local registry; a call this long is stuck.
CF_PROJECTS_TIMEOUT_SECONDS: Final = 30.0

_ID_KEY: Final = "id"
_NAME_KEY: Final = "name"

#: Project id to project name.
type ProjectNames = dict[str, str]


def project_names(run: CfRun) -> ProjectNames | CfCallFailed:
    """Every registered project's name by id, from one ``cf`` call.

    Anything but a JSON array of objects with a string ``id`` and ``name`` is a
    ``CfCallFailed`` quoting the output head.
    """
    argv = [CF_EXECUTABLE, *list_projects_command()]
    shown = " ".join(argv)
    completed = run_cf(argv, run, CF_PROJECTS_TIMEOUT_SECONDS)
    if isinstance(completed, CfCallFailed):
        return completed
    head = output_head(completed)
    if completed.returncode != 0:
        return CfCallFailed(f"`{shown}` exited {completed.returncode}: {head}")
    try:
        document: object = json.loads(completed.stdout)
    except json.JSONDecodeError:
        # Expected: CF printed something that is not JSON; reported, never guessed.
        return CfCallFailed(f"`{shown}` printed no JSON: {head!r}")
    if not isinstance(document, list):
        return CfCallFailed(f"`{shown}` did not print a JSON array: {head!r}")
    names: ProjectNames = {}
    for entry in document:  # pyright: ignore[reportUnknownVariableType]
        pair = _id_and_name(entry)  # pyright: ignore[reportUnknownArgumentType]
        if pair is None:
            return CfCallFailed(
                f"`{shown}` listed a project without an id and name: "
                f"{completed.stdout[:OUTPUT_HEAD_CHARS]!r}"
            )
        names[pair[0]] = pair[1]
    return names


def _id_and_name(entry: object) -> tuple[str, str] | None:
    if not isinstance(entry, dict):
        return None
    project_id = entry.get(_ID_KEY)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    name = entry.get(_NAME_KEY)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if isinstance(project_id, str) and isinstance(name, str) and project_id and name:
        return project_id, name
    return None
