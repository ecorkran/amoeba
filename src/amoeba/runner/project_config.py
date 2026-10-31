"""The per-project config: a static YAML file naming each project's pipeline (D2).

Loaded once at start and never mutated; a change needs a
restart. A named project carries its ``pipeline`` and optional ``params``; a project the
file does not name has no pipeline (:data:`PROJECT_DEFAULTS`), and there is no default
pipeline to fall back on. A bad file raises :class:`StartupFailedError` listing every
problem it can find in one pass. ``params`` are pipeline parameters and hold no
secrets: they are passed to ``sq run -p`` and journaled verbatim.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Annotated

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    StringConstraints,
    ValidationError,
)
from pydantic_core import ErrorDetails

from amoeba.process import StartupFailedError
from amoeba.runner.launch import TARGET_PARAM_KEY, param_problem


class ProjectSettings(BaseModel):
    """What one project's entry may say. An omitted key takes the default here."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: The Squadron pipeline run per slice, stored stripped; ``None`` for a project
    #: the file omits.
    pipeline: Annotated[StrictStr, StringConstraints(strip_whitespace=True)] | None = (
        None
    )
    #: Extra ``-p key=value`` pipeline parameters, passed through verbatim.
    params: dict[str, StrictStr] = Field(default_factory=dict[str, StrictStr])


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
    problems = tuple(_semantic_problems(parsed.projects))
    return problems or ProjectConfig(projects=parsed.projects)


def _semantic_problems(projects: Mapping[str, ProjectSettings]) -> Iterator[str]:
    """What the field types cannot say: a named project needs a pipeline, and its
    params must be ones ``sq run`` can take."""
    for project_id, settings in projects.items():
        where = f"projects.{project_id}"
        if not settings.pipeline:
            yield f"{where}.pipeline: required for a named project"
        for key, value in settings.params.items():
            if key == TARGET_PARAM_KEY:
                yield f"{where}.params.{key}: reserved, the Runner passes the slice"
            elif problem := param_problem(key, value):
                yield f"{where}.params.{key}: {problem}"


def _describe(item: ErrorDetails) -> str:
    where = ".".join(str(part) for part in item["loc"])
    return f"{where}: {item['msg']} (got {item['input']!r})"
