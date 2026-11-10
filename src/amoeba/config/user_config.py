"""The user-level config file (slice 222, D5): models, cost cap, answer limit,
and everything answers may be barred from authorizing.

No key has a default in code. A missing key, an unknown key and a bad value each
fail, and ``load_user_config`` reports every problem in one pass, naming the file
and the key. The default ``authorize_items`` list exists only as the example in
``docs/config-contract.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    ValidationError,
    field_validator,
)

from amoeba.answering.settings import ModelAlias

CONTRACT_DOC: Final = "docs/config-contract.md"

#: A stripped, non-empty string.
NonBlank = Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1)]


class ConfigError(Exception):
    """The config cannot be used; the message names the file and each bad key."""


class NotAuthorizedItem(BaseModel):
    """One thing answers may be barred from authorizing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Unique identifier; what members refer to in their authorize lists.
    key: NonBlank
    #: What the answer and check steps are told. Never matched on.
    description: NonBlank
    #: Phrases the deterministic answer screen matches. May be empty.
    screen_phrases: tuple[NonBlank, ...]
    denied_by_default: StrictBool


class UserConfig(BaseModel):
    """Amoeba's settings, set once per user."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Squadron model aliases for the answer step and the check step.
    answer_model: ModelAlias
    check_model: ModelAlias
    #: Cost cap of one answering run, in US dollars.
    max_cost_usd: Annotated[StrictInt | StrictFloat, Field(gt=0)]
    #: Most automatic answers one run may take.
    answer_limit: Annotated[StrictInt, Field(ge=1)]
    #: Most characters of passages an answering run is sent.
    passages_max_chars: Annotated[StrictInt, Field(ge=1)]
    #: Everything answers may be barred from authorizing. May be empty.
    authorize_items: tuple[NotAuthorizedItem, ...]

    @field_validator("authorize_items")
    @classmethod
    def _keys_are_unique(
        cls, items: tuple[NotAuthorizedItem, ...]
    ) -> tuple[NotAuthorizedItem, ...]:
        seen: set[str] = set()
        for item in items:
            if item.key in seen:
                raise ValueError(f"duplicate key {item.key!r}")
            seen.add(item.key)
        return items


def _read_document(path: Path) -> object:
    """The parsed YAML at ``path``, or ``ConfigError``."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError as error:
        raise ConfigError(f"no config at {path}; see {CONTRACT_DOC}") from error
    except OSError as error:
        raise ConfigError(f"{path}: cannot read: {error}") from error
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConfigError(f"{path}: not UTF-8: {error}") from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError(f"{path}: not YAML: {error}") from error


def _problems(path: Path, error: ValidationError) -> list[str]:
    """One line per validation problem, each naming the file and the key."""
    return [
        f"{path}: {'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
        for problem in error.errors()
    ]


def load_user_config(path: Path) -> UserConfig:
    """The config at ``path``.

    Raises:
        ConfigError: The file is missing, unreadable, not UTF-8, not YAML, not a
            mapping, or a key is missing, unknown or has a bad value. Every
            problem found is listed, one per line.
    """
    document = _read_document(path)
    if not isinstance(document, dict):
        raise ConfigError(f"{path}: the top level must be a mapping of keys")
    try:
        return UserConfig.model_validate(document)
    except ValidationError as error:
        raise ConfigError("\n".join(_problems(path, error))) from error
