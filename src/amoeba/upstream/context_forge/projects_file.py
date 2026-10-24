"""Context Forge's ``projects.json``: the watched fields, their types, and ``parse``.

CF keeps every project in one file. Amoeba watches a *projection* of one project's
entry: the pointer fields below, at project level and per worktree. ``updatedAt`` is
provenance only and ``customData`` is free text; neither is projected, so a write
that touches only those produces no change.

Outcome words are held as ``str`` here, not as the store's ``CFSnapshotOutcome``:
the store imports nothing from ``amoeba.upstream`` and this package imports nothing
from the store (``tests/upstream/test_import_direction.py``). The tenant maps
:class:`CFReadOutcome` to ``CFSnapshotOutcome``; it is the one module that knows both.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any, Final, cast

PROJECTS_FILE_NAME: Final = "projects.json"

# Projected fields, defined once (observed on CF 0.19.x; see the contract doc).
#: The projected fields other modules read by name, so they are spelled once.
FIELD_PROJECT_PATH: Final = "projectPath"
FIELD_WORKTREE_PATH: Final = "worktreePath"
FIELD_INDEX_RANGE: Final = "indexRange"

PROJECT_FIELDS: Final[tuple[str, ...]] = (
    "name",
    FIELD_PROJECT_PATH,
    "developmentPhase",
    "instruction",
    "fileArch",
    "fileSlicePlan",
    "fileSlice",
    "fileTasks",
)
WORKTREE_FIELDS: Final[tuple[str, ...]] = (
    "name",
    FIELD_WORKTREE_PATH,
    FIELD_INDEX_RANGE,
    "archDoc",
    "slicePlan",
    "developmentPhase",
    "activeSlice",
    "activeTaskFile",
    "instruction",
)

# Keys that decide which entry and which worktree a value belongs to.
_ID_KEY: Final = "id"
_WORKTREES_KEY: Final = "worktrees"
_UPDATED_AT_KEY: Final = "updatedAt"

# JSON keys of the projection as stored.
STATE_PROJECT_KEY: Final = "project"
STATE_WORKTREES_KEY: Final = "worktrees"


class _Absent(Enum):
    """The type of :data:`ABSENT`: a key missing from the file, not ``null``."""

    ABSENT = "absent"


ABSENT: Final = _Absent.ABSENT


class CFReadOutcome(StrEnum):
    """Why a file-level read of one link failed, as the parser can tell."""

    UNRECOGNIZED = "unrecognized"
    MISSING = "missing"


@dataclass(frozen=True)
class CFReadFailure:
    """The linked project could not be read. ``detail`` names the rule.

    ``file_wide`` is true when every link would fail the same way (the file is
    not JSON, or an element could be any link), false when only this link does.
    """

    outcome: CFReadOutcome
    detail: str
    file_wide: bool


@dataclass(frozen=True)
class CFProjectState:
    """One project's projected fields, holding only the keys present in the file."""

    project: Mapping[str, Any]
    worktrees: Mapping[str, Mapping[str, Any]]
    cf_updated_at: str | None

    def to_json(self) -> dict[str, Any]:
        return {
            STATE_PROJECT_KEY: dict(self.project),
            STATE_WORKTREES_KEY: {
                wid: dict(fields) for wid, fields in self.worktrees.items()
            },
        }

    @classmethod
    def from_json(
        cls, stored: Mapping[str, Any], cf_updated_at: str | None
    ) -> CFProjectState:
        """Rebuild a state from :meth:`to_json` output.

        Raises ``ValueError`` on any other shape.
        """
        project = stored.get(STATE_PROJECT_KEY)
        worktrees = stored.get(STATE_WORKTREES_KEY)
        project = _object(project)
        worktrees = _object(worktrees)
        if project is None or worktrees is None:
            raise ValueError(
                f"stored CF state lacks {STATE_PROJECT_KEY!r} and "
                f"{STATE_WORKTREES_KEY!r} objects"
            )
        if not all(isinstance(fields, dict) for fields in worktrees.values()):
            raise ValueError("stored CF state has a worktree that is not an object")
        return cls(project, worktrees, cf_updated_at)


@dataclass(frozen=True)
class CFFieldChange:
    """One field that moved. ``before``/``after`` are :data:`ABSENT` if no key."""

    worktree_id: str | None
    field: str
    before: object = ABSENT
    after: object = ABSENT

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"worktree_id": self.worktree_id, "field": self.field}
        if self.before is not ABSENT:
            out["from"] = self.before
        if self.after is not ABSENT:
            out["to"] = self.after
        return out


def _object(value: object) -> dict[str, Any] | None:
    """``value`` as a JSON object, or ``None`` if it is anything else."""
    return cast("dict[str, Any]", value) if isinstance(value, dict) else None


def _project_of(
    entry: Mapping[str, Any], worktrees: Mapping[str, Mapping[str, Any]]
) -> CFProjectState:
    updated = entry.get(_UPDATED_AT_KEY)
    return CFProjectState(
        project={field: entry[field] for field in PROJECT_FIELDS if field in entry},
        worktrees=worktrees,
        cf_updated_at=updated if isinstance(updated, str) else None,
    )


def _worktrees_of(entry: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]] | str:
    """The projected worktrees, or the detail of the rule ``worktrees`` breaks."""
    if _WORKTREES_KEY not in entry:
        return {}
    raw = entry[_WORKTREES_KEY]
    if not isinstance(raw, list):
        return "worktrees is present but is not an array"
    out: dict[str, Mapping[str, Any]] = {}
    for raw_item in cast("list[object]", raw):
        item = _object(raw_item)
        if item is None or not isinstance(item.get(_ID_KEY), str):
            return "a worktree is not an object with a string id"
        wid: str = item[_ID_KEY]
        if wid in out:
            return f"worktree id {wid!r} appears more than once"
        out[wid] = {field: item[field] for field in WORKTREE_FIELDS if field in item}
    return out


def parse(data: bytes, cf_project_id: str) -> CFProjectState | CFReadFailure:
    """Read one project's projection out of the bytes of ``projects.json``.

    File-level defects return the same failure for every id; defects in the linked
    entry or its worktrees apply to that link only. Projected values are not
    type-checked: they are copied as CF wrote them.
    """
    try:
        document = json.loads(data)
    except ValueError as error:
        # JSONDecodeError and UnicodeDecodeError: CF validates before it renames,
        # so a bad file is a real finding, not a race.
        return CFReadFailure(
            CFReadOutcome.UNRECOGNIZED, f"not valid JSON: {error}", file_wide=True
        )
    if not isinstance(document, list):
        return CFReadFailure(
            CFReadOutcome.UNRECOGNIZED, "top level is not an array", file_wide=True
        )
    entries: list[dict[str, Any]] = []
    for index, element in enumerate(cast("list[object]", document)):
        entry = _object(element)
        if entry is None or not isinstance(entry.get(_ID_KEY), str):
            return CFReadFailure(
                CFReadOutcome.UNRECOGNIZED,
                f"element {index} is not an object with a string id",
                file_wide=True,
            )
        entries.append(entry)
    matches = [entry for entry in entries if entry[_ID_KEY] == cf_project_id]
    if not matches:
        return CFReadFailure(
            CFReadOutcome.MISSING,
            f"no project has id {cf_project_id!r}",
            file_wide=False,
        )
    if len(matches) > 1:
        return CFReadFailure(
            CFReadOutcome.UNRECOGNIZED,
            f"id {cf_project_id!r} appears more than once",
            file_wide=False,
        )
    worktrees = _worktrees_of(matches[0])
    if isinstance(worktrees, str):
        return CFReadFailure(CFReadOutcome.UNRECOGNIZED, worktrees, file_wide=False)
    return _project_of(matches[0], worktrees)
