"""``hub.yaml``: how the hub listens, where it backs up and how much it logs
(slice 260, D14).

No key has a default in code. A missing key, an unknown key and a bad value each
fail, and ``load_hub_config`` reports every problem in one pass, naming the file and
the key, as ``load_user_config`` does.
"""

from __future__ import annotations

from pathlib import Path, PurePath
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    ValidationError,
    field_validator,
)

from amoeba.config.user_config import (
    ConfigError,
    read_yaml_document,
    validation_problems,
)
from amoeba.wire.address import PORT_MAX, PORT_MIN, split_address

type NonBlankText = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1)
]


class HubConfigError(ConfigError):
    """``hub.yaml`` cannot be used; the message names the file and each bad key."""


class HubConfig(BaseModel):
    """The eight keys of ``hub.yaml`` (D14)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: The interface to listen on.
    bind: NonBlankText
    #: The port to listen on.
    port: Annotated[StrictInt, Field(ge=PORT_MIN, le=PORT_MAX)]
    #: ``host:port`` that clients are told to connect to, printed in join lines.
    address: NonBlankText
    #: Where backups go: absolute, and on another disk if the hub's store is to
    #: survive that disk.
    backup_dir: NonBlankText
    backup_hours: Annotated[StrictInt | StrictFloat, Field(gt=0)]
    backups_kept: Annotated[StrictInt, Field(ge=1)]
    hub_log_max_bytes: Annotated[StrictInt, Field(ge=1)]
    #: Counting the current file.
    hub_logs_kept: Annotated[StrictInt, Field(ge=2)]

    @field_validator("address")
    @classmethod
    def _host_and_port(cls, value: str) -> str:
        split_address(value)
        return value

    @field_validator("backup_dir")
    @classmethod
    def _absolute(cls, value: str) -> str:
        if not PurePath(value).is_absolute():
            raise ValueError("must be an absolute path")
        return value

    @property
    def backup_path(self) -> Path:
        return Path(self.backup_dir)


def load_hub_config(path: Path) -> HubConfig:
    """The hub config at ``path``.

    Raises:
        HubConfigError: The file is missing, unreadable, not YAML, not a mapping, or
            a key is missing, unknown or has a bad value. Every problem found is
            listed, one per line, naming the file and the key.
    """
    try:
        document = read_yaml_document(path, kind="hub config")
        if not isinstance(document, dict):
            raise ConfigError(f"{path}: the top level must be a mapping of keys")
        return HubConfig.model_validate(document)
    except ConfigError as error:
        raise HubConfigError(str(error)) from error
    except ValidationError as error:
        raise HubConfigError("\n".join(validation_problems(path, error))) from error
