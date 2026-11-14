"""Fakes for the ``list`` tests: one ``cf`` that answers both lookups it is asked."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cf_fixtures import failure

from amoeba.upstream.context_forge.projects import ProjectNames
from operations.status_support import CfAnswer, FakeCf

LIST_ARGUMENT = "list"


def project_entry(
    project_id: str, name: str, path: str | None = None
) -> dict[str, Any]:
    """One ``cf list projects --json`` entry; CF omits ``projectPath`` on some."""
    entry: dict[str, Any] = {"id": project_id, "name": name, "isActive": False}
    if path is not None:
        entry["projectPath"] = path
    return entry


@dataclass
class ListCf:
    """``cf list projects --json`` prints ``projects``; ``cf get`` goes to ``FakeCf``.

    ``projects`` of ``None`` makes the listing fail.
    """

    projects: Sequence[dict[str, Any]] | None
    by_directory: Mapping[Path, str | CfAnswer] = field(
        default_factory=lambda: dict[Path, str | CfAnswer]()
    )
    listings: int = 0

    def __call__(
        self, argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if LIST_ARGUMENT in argv:
            self.listings += 1
            if self.projects is None:
                return failure(argv)
            return subprocess.CompletedProcess(
                list(argv), 0, json.dumps(list(self.projects)), ""
            )
        return FakeCf(self.by_directory)(argv, **kwargs)


def names_of(projects: Sequence[dict[str, Any]]) -> ProjectNames:
    return {entry["id"]: entry["name"] for entry in projects}
