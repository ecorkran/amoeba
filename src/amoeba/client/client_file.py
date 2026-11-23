"""The client file, ``client.yaml``: which hub this machine uses (slice 260, D3).

Exactly three keys: ``address`` (``host:port``), ``machine`` and ``token``. It is
written through one fixed temporary name and a rename with mode ``0600``, and loading
refuses a file anyone but the owner can read.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    StrictStr,
    ValidationError,
    field_validator,
)

from amoeba.client.errors import ClientFileError
from amoeba.wire.address import split_address
from amoeba.wire.atomic_file import PRIVATE_FILE_MODE, write_through_rename

#: Mode bits that must be clear: group and other.
_OTHERS_MASK: Final = 0o077
ADDRESS_KEY: Final = "address"
JOIN_AGAIN_ADVICE: Final = (
    "run `amoeba join` again with a new line from `amoeba hub invite`"
)


class ClientFile(BaseModel):
    """What `amoeba join` saved."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    address: StrictStr
    machine: StrictStr
    token: StrictStr

    @field_validator("address")
    @classmethod
    def _host_and_port(cls, value: str) -> str:
        split_address(value)
        return value


def write_client_file(path: Path, client_file: ClientFile) -> None:
    """Write the file with mode ``0600`` through a temporary name and a rename."""
    # The token in it is the machine's credential, so the mode is private.
    text = yaml.safe_dump(client_file.model_dump(), sort_keys=False)
    write_through_rename(path, text.encode("utf-8"), PRIVATE_FILE_MODE)


def _read_mapping(path: Path) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ClientFileError(
            f"{path}: cannot read the client file: {error}"
        ) from error
    try:
        document = yaml.safe_load(raw)
    except yaml.YAMLError as error:
        raise ClientFileError(f"{path}: not YAML: {error}") from error
    if not isinstance(document, dict):
        raise ClientFileError(f"{path}: the top level must be a mapping of keys")
    return {str(key): value for key, value in document.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


def load_client_file(path: Path, pinned_cert_path: Path) -> ClientFile:
    """The client file at ``path``, checked.

    Raises:
        ClientFileError: Anyone but the owner can read the file; a key is missing or
            unknown; or the saved certificate at ``pinned_cert_path`` is missing or
            unreadable. Each message names the file.
    """
    mode = path.stat().st_mode if path.exists() else None
    if mode is not None and mode & _OTHERS_MASK:
        raise ClientFileError(
            f"{path} is readable by others and holds this machine's token; "
            f"run `chmod 600 {path}`"
        )
    document = _read_mapping(path)
    try:
        client_file = ClientFile.model_validate(document)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in problem['loc']) or 'file'}: "
            f"{problem['msg']}"
            for problem in error.errors()
        )
        raise ClientFileError(f"{path}: {problems}") from error
    try:
        pinned_cert_path.read_bytes()
    except OSError as error:
        raise ClientFileError(
            f"the saved hub certificate {pinned_cert_path} is missing or unreadable "
            f"({error.strerror or error}); {JOIN_AGAIN_ADVICE}"
        ) from error
    return client_file


def read_client_address(path: Path) -> str:
    """The ``address`` key alone, for messages that name the hub.

    Never fails on a missing certificate.

    Raises:
        ClientFileError: The file cannot be read or holds no text ``address``.
    """
    address = _read_mapping(path).get(ADDRESS_KEY)
    if not isinstance(address, str):
        raise ClientFileError(f"{path}: {ADDRESS_KEY} is missing or not text")
    return address
