"""Context Forge link and snapshot records, and the snapshot outcome word list.

``CFSnapshotOutcome`` is defined here and nowhere else in Python; migration
``008``'s trigger fires for every outcome and repeats none of the words. Like
``check_models.py`` this module knows nothing about SQL, ``sqlite3``, or pydantic,
and nothing about ``amoeba.upstream``: ``state`` and ``changed`` are plain
JSON-compatible values the store stores and returns without interpreting them.
The tenant (``amoeba.process.cf_watch``) is the one module that knows both sides.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CFSnapshotOutcome(StrEnum):
    """What the watch saw when it looked at one link."""

    OBSERVED = "observed"
    UNREADABLE = "unreadable"
    UNRECOGNIZED = "unrecognized"
    MISSING = "missing"


@dataclass(frozen=True)
class CFLink:
    """A Context Forge project an Amoeba project watches. Permanent once made."""

    project_id: str
    cf_project_id: str
    linked_at: datetime


@dataclass(frozen=True, kw_only=True)
class CFSnapshotInput:
    """What the watch records about one link at one check.

    ``state`` and ``changed`` are set exactly when ``outcome`` is ``observed``;
    ``detail`` is set exactly when it is not. ``observed_at`` is when the watch
    read the file: the store reads no clock for it.
    """

    project_id: str
    cf_project_id: str
    outcome: CFSnapshotOutcome
    state: Mapping[str, object] | None
    changed: Sequence[Mapping[str, object]] | None
    detail: str | None
    cf_updated_at: str | None
    cf_version_label: str
    observed_at: datetime


@dataclass(frozen=True, kw_only=True)
class CFSnapshot(CFSnapshotInput):
    """A recorded snapshot. ``id`` is arrival order and the feed's ``subject_id``."""

    id: int
