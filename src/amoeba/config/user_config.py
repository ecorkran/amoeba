"""The user-level config file (slice 222, D5): models, cost cap, answer limit,
and everything answers may be barred from authorizing.

No key has a default in code. A missing key, an unknown key and a bad value each
fail, and ``load_user_config`` reports every problem in one pass, naming the file
and the key. The default ``authorize_items`` list exists only as the example in
``docs/config-contract.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final, cast

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
    model_validator,
)

from amoeba.answering.settings import ModelAlias, RulesPath
from amoeba.store.vocabulary import ConsumedMode

#: The command a missing config points at. It writes a complete starter config.
INIT_HINT: Final = "amoeba init"
#: The longest a request may stay open: ten years, in hours. Stated in the contract.
MAX_REQUEST_OPEN_TTL_HOURS: Final = 24 * 365 * 10
#: ``session_stale_seconds`` is at least this many heartbeats, so one missed beat
#: does not read as a session gone (slice 241, D7).
STALE_HEARTBEATS_MIN: Final = 2

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
    #: Longest an answering run may take before it is stopped, in seconds (slice 223).
    answering_wait_seconds: Annotated[StrictInt | StrictFloat, Field(gt=0)]
    #: Longest a resumed run may take to start running before the resume is judged
    #: refused, in seconds (slice 223).
    resume_wait_seconds: Annotated[StrictInt | StrictFloat, Field(gt=0)]
    #: Age in days after which settled scratch, logs and calls-log days are removed
    #: (slice 228, D9).
    prune_after_days: Annotated[StrictInt, Field(ge=1)]
    #: Hours an open request waits for an answer before it expires; fixed into each
    #: request at send (slice 240, D12). Bounded so ``created_at`` plus the TTL is
    #: always a time the store can hold.
    request_open_ttl_hours: Annotated[
        StrictInt, Field(ge=1, le=MAX_REQUEST_OPEN_TTL_HOURS)
    ]
    #: Deepest a chain of requests may go; a send whose parent is this deep is
    #: rejected (slice 240, D8, D12).
    max_chain_depth: Annotated[StrictInt, Field(ge=1)]
    #: How often ``amoeba-mcp`` checks its member's deliveries for push, in seconds
    #: (slice 241, D2, D7).
    notify_poll_seconds: Annotated[StrictInt | StrictFloat, Field(gt=0)]
    #: How often a serving ``amoeba-mcp`` writes its session row (slice 241, D6).
    session_heartbeat_seconds: Annotated[StrictInt | StrictFloat, Field(gt=0)]
    #: Age of a session's last heartbeat past which it counts as gone (slice 241, D6).
    session_stale_seconds: Annotated[StrictInt | StrictFloat, Field(gt=0)]
    #: Longest a woken agent's command may run before its wrapper stops it, in
    #: seconds; fixed into each wake at the claim (slice 244, D7, D8).
    wake_timeout_seconds: Annotated[StrictInt | StrictFloat, Field(gt=0)]
    #: Most wakes started for one member in any rolling 24 hours, failed starts
    #: included (slice 244, D7, D8).
    max_wakes_per_day: Annotated[StrictInt, Field(ge=1)]
    #: Rules files a member that names none reads, each skipped when absent
    #: (slice 229, D7, D8). Not empty: a default of no rules is ``--no-rules``.
    default_rules_paths: Annotated[tuple[RulesPath, ...], Field(min_length=1)]
    #: Which of a provider's reports a ``--depends-on`` without a mode consumes.
    default_consumed: ConsumedMode
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

    @model_validator(mode="after")
    def _session_timing_holds(self) -> UserConfig:
        """The heartbeat is no more often than the push check, and the stale limit
        spans at least ``STALE_HEARTBEATS_MIN`` beats; each failure names both keys."""
        if self.session_heartbeat_seconds < self.notify_poll_seconds:
            raise ValueError(
                "session_heartbeat_seconds must be at least notify_poll_seconds"
            )
        if self.session_stale_seconds < (
            STALE_HEARTBEATS_MIN * self.session_heartbeat_seconds
        ):
            raise ValueError(
                f"session_stale_seconds must be at least {STALE_HEARTBEATS_MIN} "
                "times session_heartbeat_seconds"
            )
        return self


def read_config_text(path: Path) -> str:
    """The text of the config at ``path``, or ``ConfigError``."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError as error:
        raise ConfigError(
            f"no config at {path}; run `{INIT_HINT}` to create one"
        ) from error
    except OSError as error:
        raise ConfigError(f"{path}: cannot read: {error}") from error
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConfigError(f"{path}: not UTF-8: {error}") from error


def config_document(path: Path, text: str) -> dict[str, object]:
    """``text`` parsed as a config mapping; ``path`` only names the file in errors."""
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError(f"{path}: not YAML: {error}") from error
    if not isinstance(document, dict):
        raise ConfigError(f"{path}: the top level must be a mapping of keys")
    return cast("dict[str, object]", document)


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
    return user_config_from_text(path, read_config_text(path))


def user_config_from_text(path: Path, text: str) -> UserConfig:
    """The config in ``text``; ``path`` only names the file in each problem.

    Raises:
        ConfigError: As ``load_user_config``, for everything but reading the file.
    """
    try:
        return UserConfig.model_validate(config_document(path, text))
    except ValidationError as error:
        raise ConfigError("\n".join(_problems(path, error))) from error
