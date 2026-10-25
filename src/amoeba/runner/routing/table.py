"""The routing table: a YAML file of ordered rules, versioned by digest (D2).

``parse_table`` reads the text, validates it and returns a frozen
:class:`RoutingTable`. Every problem is reported at once in one
:class:`TableError`; a caller never sees ``yaml.YAMLError`` or a pydantic error.
The table is never mutated: a new file is a new table with a new version.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
)
from pydantic_core import ErrorDetails

from amoeba.runner.routing.inputs import RoutingInput
from amoeba.runner.routing.validate import (
    PARAMETER_JUDGE_ELIGIBLE,
    PARAMETER_MAX_ATTEMPTS,
    SUPPORTED_FORMATS,
    normalize_condition,
    normalize_input_name,
    normalize_route,
    validate,
)
from amoeba.store import Route

__all__ = [
    "SUPPORTED_FORMATS",
    "VERSION_PREFIX",
    "Rule",
    "RuleFile",
    "RoutingTable",
    "TableError",
    "TableFile",
    "load_table",
    "parse_table",
]

#: A table's version label is this prefix plus the hex digest of its bytes.
VERSION_PREFIX: Final = "sha256:"

#: A condition value as YAML delivers it: text, or a bare ``true``/``no`` boolean.
ConditionValue = StrictStr | StrictBool


class TableError(Exception):
    """A table that cannot be used, with every problem found."""

    def __init__(self, problems: tuple[str, ...]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


class RuleFile(BaseModel):
    """One rule as written in the file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: StrictStr
    when: dict[StrictStr, ConditionValue | list[ConditionValue]] = Field(
        default_factory=dict
    )
    route: StrictStr
    max_attempts: StrictInt | None = None
    judge_eligible: StrictBool | None = None


class TableFile(BaseModel):
    """A table file as written."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    format: StrictInt
    time_bounds_minutes: dict[StrictStr, StrictInt]
    rules: list[RuleFile]


@dataclass(frozen=True)
class Rule:
    """A validated rule. Exactly the parameters of its route are set."""

    id: str
    when: Mapping[RoutingInput, frozenset[str]]
    route: Route
    max_attempts: int | None
    judge_eligible: bool | None

    @property
    def parameters(self) -> Mapping[str, int | bool]:
        """The rule's route parameters, as recorded with each decision."""
        found: dict[str, int | bool] = {}
        if self.max_attempts is not None:
            found[PARAMETER_MAX_ATTEMPTS] = self.max_attempts
        if self.judge_eligible is not None:
            found[PARAMETER_JUDGE_ELIGIBLE] = self.judge_eligible
        return found


@dataclass(frozen=True)
class RoutingTable:
    """A loaded table: its version, the text it came from, and its rules."""

    version: str
    content: str
    rules: tuple[Rule, ...]
    time_bounds_minutes: Mapping[str, int]


def table_version(text: str) -> str:
    """``sha256:`` plus the hex digest of the text's UTF-8 bytes."""
    return VERSION_PREFIX + hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_table(text: str) -> RoutingTable:
    """Parse and validate ``text``.

    Raises:
        TableError: Listing every problem found.
    """
    file = _read_file(text)
    problems = validate(file)
    if problems:
        raise TableError(tuple(problems))
    return RoutingTable(
        version=table_version(text),
        content=text,
        rules=tuple(_rule_of(rule) for rule in file.rules),
        time_bounds_minutes=dict(file.time_bounds_minutes),
    )


def load_table(path: Path) -> RoutingTable:
    """Read the file at ``path`` as UTF-8 and parse it.

    Raises:
        TableError: The file is missing, unreadable or not UTF-8, or its content
            has problems. The path is named.
    """
    try:
        text = path.read_bytes().decode("utf-8")
    except OSError as error:
        # Expected: a missing path, a directory, no permission. The caller needs
        # the path and the reason, as a problem, not a traceback.
        raise TableError((f"cannot read the routing table {path}: {error}",)) from error
    except UnicodeDecodeError as error:
        # Expected: the file is not text. Same answer as an unreadable file.
        raise TableError(
            (f"the routing table {path} is not UTF-8 text: {error}",)
        ) from error
    try:
        return parse_table(text)
    except TableError as error:
        raise TableError(
            tuple(f"{path}: {problem}" for problem in error.problems)
        ) from error


def _read_file(text: str) -> TableFile:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as error:
        # Expected: a table that is not YAML. Reported as the one problem.
        raise TableError((f"the table is not valid YAML: {error}",)) from error
    if not isinstance(raw, dict):
        raise TableError(("the table must be a YAML mapping with format, rules, ...",))
    try:
        return TableFile.model_validate(raw)
    except ValidationError as error:
        # Expected: a field of the wrong shape. Each error becomes a problem.
        raise TableError(tuple(_describe(item) for item in error.errors())) from error


def _describe(item: ErrorDetails) -> str:
    where = ".".join(str(part) for part in item["loc"])
    return f"{where}: {item['msg']}"


def _rule_of(rule: RuleFile) -> Rule:
    return Rule(
        id=rule.id,
        when={
            RoutingInput(normalize_input_name(name)): normalize_condition(values)
            for name, values in rule.when.items()
        },
        route=normalize_route(rule.route),
        max_attempts=rule.max_attempts,
        judge_eligible=rule.judge_eligible,
    )
