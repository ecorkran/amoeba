"""Context Forge's projects (slices 224, 229): ``cf list projects --json``.

Members are stored by project id only; a name and a path are read when a result is
shown and never stored. ``id`` and ``name`` are required on every entry;
``projectPath`` is missing on some, so it is ``None`` there; ``fileSlice`` and
``isActive`` are not wanted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
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
_PATH_KEY: Final = "projectPath"


@dataclass(frozen=True)
class ProjectDetail:
    id: str
    name: str
    #: Where the project is checked out; ``None`` when Context Forge has no path.
    path: str | None


#: Project id to project name.
type ProjectNames = dict[str, str]
#: Project id to its details.
type ProjectDetails = dict[str, ProjectDetail]


def project_names(run: CfRun) -> ProjectNames | CfCallFailed:
    """Every registered project's name by id, from one ``cf`` call.

    Anything but a JSON array of objects with a string ``id`` and ``name`` is a
    ``CfCallFailed`` quoting the output head.
    """
    details = project_details(run)
    if isinstance(details, CfCallFailed):
        return details
    return {project_id: detail.name for project_id, detail in details.items()}


def project_details(run: CfRun) -> ProjectDetails | CfCallFailed:
    """Every registered project's id, name and path (or ``None``), one ``cf`` call.

    The same call and the same failures as :func:`project_names`.
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
    details: ProjectDetails = {}
    for entry in document:  # pyright: ignore[reportUnknownVariableType]
        detail = _detail(entry)  # pyright: ignore[reportUnknownArgumentType]
        if detail is None:
            return CfCallFailed(
                f"`{shown}` listed a project without an id and name: "
                f"{completed.stdout[:OUTPUT_HEAD_CHARS]!r}"
            )
        details[detail.id] = detail
    return details


def _detail(entry: object) -> ProjectDetail | None:
    if not isinstance(entry, dict):
        return None
    project_id = entry.get(_ID_KEY)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    name = entry.get(_NAME_KEY)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    path = entry.get(_PATH_KEY)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if not (isinstance(project_id, str) and isinstance(name, str)):
        return None
    if not (project_id and name):
        return None
    # A path of another type, or an empty one, is no path: CF omits it on some entries.
    return ProjectDetail(
        project_id, name, path if isinstance(path, str) and path else None
    )
