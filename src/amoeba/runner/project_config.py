"""The per-project config: a static YAML file holding the merge policy (slice 128, D8).

Loaded once at start, like the routing table, and never mutated; a change needs a
restart. With no file, every project takes :data:`PROJECT_DEFAULTS`, the one place a
default lives. A bad file raises :class:`StartupFailedError` listing every problem.
The file holds no secrets.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator
from pydantic_core import ErrorDetails

from amoeba.process import StartupFailedError


class MergePolicy(StrEnum):
    """Who merges a slice into its target after its code review passes."""

    #: The PM merges; ``P6`` runs with ``-p merge=false``.
    HUMAN = "human"
    #: ``P6`` merges the slice itself.
    AUTO = "auto"


class ProjectSettings(BaseModel):
    """What one project's entry may say. An omitted key takes the default here."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    merge_policy: MergePolicy = MergePolicy.HUMAN

    @field_validator("merge_policy", mode="before")
    @classmethod
    def _normalise(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value


class ProjectConfigFile(BaseModel):
    """The file's shape: Amoeba project ids under ``projects``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    projects: dict[str, ProjectSettings] = {}


#: The settings of a project the file does not name.
PROJECT_DEFAULTS = ProjectSettings()


@dataclass(frozen=True)
class ProjectConfig:
    """The loaded config: each named project's settings, defaults for the rest."""

    projects: Mapping[str, ProjectSettings] = MappingProxyType({})

    def for_project(self, project_id: str) -> ProjectSettings:
        """The settings for ``project_id``; a project the file omits gets defaults."""
        return self.projects.get(project_id, PROJECT_DEFAULTS)


def load_project_config(path: Path | None) -> ProjectConfig:
    """Load the config file; ``None`` means every project takes the defaults.

    Raises:
        StartupFailedError: The file is missing, unreadable or not UTF-8, is not
            YAML, or holds an unknown key or value. Every problem is listed.
    """
    if path is None:
        return ProjectConfig()
    problems = _problems_or_config(path)
    if isinstance(problems, ProjectConfig):
        return problems
    raise StartupFailedError(
        f"project config {path} is invalid:\n" + "\n".join(f"  - {p}" for p in problems)
    )


def _problems_or_config(path: Path) -> ProjectConfig | tuple[str, ...]:
    try:
        text = path.read_bytes().decode("utf-8")
    except OSError as error:
        # Expected: a missing path, a directory, no permission. Reported as the problem.
        return (f"cannot read the file: {error}",)
    except UnicodeDecodeError as error:
        # Expected: the file is not text. Same answer as an unreadable file.
        return (f"the file is not UTF-8 text: {error}",)
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as error:
        # Expected: a config that is not YAML. Reported as the one problem.
        return (f"not valid YAML: {error}",)
    if not isinstance(raw, dict):
        return ("the file must be a YAML mapping with a `projects` key",)
    try:
        parsed = ProjectConfigFile.model_validate(raw)
    except ValidationError as error:
        # Expected: a wrong key or value. Each error becomes a problem.
        return tuple(_describe(item) for item in error.errors())
    return ProjectConfig(projects=parsed.projects)


def _describe(item: ErrorDetails) -> str:
    where = ".".join(str(part) for part in item["loc"])
    return f"{where}: {item['msg']} (got {item['input']!r})"
