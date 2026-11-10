"""The Amoeba home: the one directory holding the store and the user config.

This module holds the only read of ``AMOEBA_HOME`` and the only use of
``Path.home``. Everything else asks these functions, and only the process
boundary (the CLI, the MCP layer) does that; operations take a store and a config
as arguments. ``XDG_CONFIG_HOME`` is never consulted: there is one way to choose
the location.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

#: The variable that redirects the home, read at call time (D1).
HOME_VARIABLE: Final = "AMOEBA_HOME"
#: Where the home is when the variable is unset, relative to the user's home.
DEFAULT_HOME_PARTS: Final = (".config", "amoeba")
STORE_FILE_NAME: Final = "amoeba.sqlite3"
CONFIG_FILE_NAME: Final = "config.yaml"
#: Scratch directories of answering runs, one per run id (slice 223, D12).
ANSWERING_DIR_NAME: Final = "answering"
#: Stdout and stderr logs of answering runs and resumes.
LOGS_DIR_NAME: Final = "logs"
#: Squadron's run files, relative to the user's home. Read only by ``run_file``.
SQUADRON_RUNS_PARTS: Final = (".config", "squadron", "runs")


class AmoebaHomeError(Exception):
    """``AMOEBA_HOME`` is set to something that cannot name the home."""


def amoeba_home() -> Path:
    """The home directory: ``$AMOEBA_HOME``, else ``~/.config/amoeba``.

    Resolved at every call, never at import, so a test can redirect it.

    Raises:
        AmoebaHomeError: the variable is set but empty or relative. It never
            falls back to the default.
    """
    value = os.environ.get(HOME_VARIABLE)
    if value is None:
        return Path.home().joinpath(*DEFAULT_HOME_PARTS)
    if not value.strip():
        raise AmoebaHomeError(f"{HOME_VARIABLE} is set but empty")
    home = Path(value)
    if not home.is_absolute():
        raise AmoebaHomeError(
            f"{HOME_VARIABLE} must be an absolute path, got {value!r}"
        )
    return home


def store_path() -> Path:
    """The SQLite store file under the home."""
    return amoeba_home() / STORE_FILE_NAME


def config_path() -> Path:
    """The user config file under the home."""
    return amoeba_home() / CONFIG_FILE_NAME


def answering_dir() -> Path:
    """Where each answering run's scratch directory lives, under the home."""
    return amoeba_home() / ANSWERING_DIR_NAME


def logs_dir() -> Path:
    """Where answering and resume logs live, under the home."""
    return amoeba_home() / LOGS_DIR_NAME


def squadron_runs_dir() -> Path:
    """Squadron's run-file directory, ``~/.config/squadron/runs``."""
    return Path.home().joinpath(*SQUADRON_RUNS_PARTS)
