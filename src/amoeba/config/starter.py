"""The starter config: the one complete, valid ``config.yaml`` Amoeba ships.

``amoeba init`` writes it on a new machine and fills an older config's missing keys
from it. It is the single source of the values under ``## Example`` in
``docs/config-contract.md``; a test keeps the two equal.

The loader still has no default for any key. A value reaches a run only through the
file a person can read and edit, which this module writes once and never overwrites.
"""

from __future__ import annotations

import os
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
PARTIAL_SUFFIX: Final = ".amoeba-partial"


def starter_text() -> str:
    """The starter config as shipped, comments included."""
    return Path(__file__).with_name(STARTER_FILE_NAME).read_text(encoding="utf-8")


def starter_values() -> dict[str, Any]:
    """The starter config's keys and values."""
    return cast("dict[str, Any]", yaml.safe_load(starter_text()))


def _replace(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` in one step, so a reader never sees half a file."""
    partial = path.with_name(path.name + PARTIAL_SUFFIX)
    partial.write_text(text, encoding="utf-8")
    os.replace(partial, path)


def write_starter(path: Path) -> None:
    """Create ``path`` (and its directory) holding the starter config."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _replace(path, starter_text())


def fill_missing_keys(path: Path, values: dict[str, Any]) -> list[str]:
    """Add each required key the config at ``path`` lacks, taken from ``values``.

    The file is replaced only when the result is a valid config, so a config with any
    other fault is reported and left exactly as it was.

    Returns:
        The keys added; empty when the file was already complete.

    Raises:
        ConfigError: The file is missing or unreadable, a missing key has no value
            in ``values``, or the result is not a valid config.
    """
    text = read_config_text(path)
    present = config_document(path, text)
    missing = [key for key in UserConfig.model_fields if key not in present]
    unknown = [key for key in missing if key not in values]
    if unknown:
        raise ConfigError(f"{path} lacks {unknown} and there is no example for them")
    if not missing:
        user_config_from_text(path, text)
        return []
    addition = yaml.safe_dump({key: values[key] for key in missing}, sort_keys=False)
    filled = text + ("" if text.endswith("\n") else "\n") + addition
    user_config_from_text(path, filled)
    _replace(path, filled)
    return missing
