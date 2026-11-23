"""The starter config: the one complete, valid ``config.yaml`` Amoeba ships.

``amoeba init`` writes it on a new machine and fills an older config's missing keys
from it. ``starter_config.yaml`` is the single source of the suggested values; the
block under ``## Example`` in ``docs/config-contract.md`` shows the same ones, and a
test keeps the two equal.

The loader still has no default for any key. A value reaches a run only through the
file a person can read and edit. This module adds keys to that file and never changes
a value that is already in it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, cast

import yaml

from amoeba.config.user_config import (
    ConfigError,
    UserConfig,
    config_document,
    read_config_text,
    user_config_from_text,
)

STARTER_FILE_NAME: Final = "starter_config.yaml"
COMMENT_MARK: Final = "#"


def starter_text() -> str:
    """The starter config as shipped, comments included."""
    return Path(__file__).with_name(STARTER_FILE_NAME).read_text(encoding="utf-8")


def starter_values() -> dict[str, Any]:
    """The starter config's keys and values."""
    return cast("dict[str, Any]", yaml.safe_load(starter_text()))


def _write(path: Path, text: str) -> None:
    """Write ``text`` through ``path``, creating its directory.

    Written through the path and not swapped in beside it, so a config that is a link
    (into a dotfiles repo, say) keeps pointing where it did and keeps its mode.

    Raises:
        ConfigError: The directory or the file cannot be written.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"{path}: cannot write: {error}") from error


def write_starter(path: Path) -> None:
    """Create ``path`` (and its directory) holding the starter config."""
    _write(path, starter_text())


def _holds_no_keys(text: str) -> bool:
    """Whether a config file is empty or only comments: nothing a person set."""
    lines = (line.strip() for line in text.splitlines())
    return all(not line or line.startswith(COMMENT_MARK) for line in lines)


def fill_missing_keys(path: Path, values: dict[str, Any]) -> list[str]:
    """Add each required key the config at ``path`` lacks, taken from ``values``.

    The file is written only when the result is a valid config, so a config with any
    other fault is reported and left exactly as it was.

    Returns:
        The keys added; empty when the file was already complete.

    Raises:
        ConfigError: The file is missing, unreadable or cannot be written, a missing
            key has no value in ``values``, or the result is not a valid config.
    """
    text = read_config_text(path)
    present = {} if _holds_no_keys(text) else config_document(path, text)
    missing = [key for key in UserConfig.model_fields if key not in present]
    unknown = [key for key in missing if key not in values]
    if unknown:
        raise ConfigError(f"{path} lacks {unknown} and there is no example for them")
    if not missing:
        user_config_from_text(path, text)
        return []
    addition = yaml.safe_dump({key: values[key] for key in missing}, sort_keys=False)
    filled = text + ("" if not text or text.endswith("\n") else "\n") + addition
    user_config_from_text(path, filled)
    _write(path, filled)
    return missing
