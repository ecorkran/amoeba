"""The Amoeba homes: where config lives and where state lives.

This module holds the only read of ``AMOEBA_HOME`` and the only use of
``Path.home``. Everything else asks these functions, and only ``cli``, ``mcp`` and
``wiring`` call ``state_layout()``, ``config_home()`` and ``state_home()``;
operations take a store, a config and a ``StateLayout`` as arguments.
``XDG_CONFIG_HOME`` and ``XDG_STATE_HOME`` are never consulted: there is one way to
choose the location, because the hook and the shell may differ in the XDG variables
and would silently use different stores.

Config (``config.yaml``, edited by a person) lives in the config home. The store,
answering scratch and logs (state) live in the state home. ``AMOEBA_HOME``, when
set, is both, so a test redirects everything to one directory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: The variable that redirects both homes, read at call time (222 D1, 228 D1).
HOME_VARIABLE: Final = "AMOEBA_HOME"
#: Where the config home is when the variable is unset, relative to the user's home.
DEFAULT_CONFIG_HOME_PARTS: Final = (".config", "amoeba")
#: Where the state home is when the variable is unset, relative to the user's home.
DEFAULT_STATE_HOME_PARTS: Final = (".local", "state", "amoeba")
STORE_FILE_NAME: Final = "amoeba.sqlite3"
CONFIG_FILE_NAME: Final = "config.yaml"
#: Scratch directories of answering runs, one per run id (slice 223, D12).
ANSWERING_DIR_NAME: Final = "answering"
#: Stdout and stderr logs of answering runs and resumes.
LOGS_DIR_NAME: Final = "logs"
#: One JSONL file per UTC day of ``handle_pause`` calls, under the logs (228 D11).
CALLS_LOG_DIR_NAME: Final = "calls"
#: Squadron's run files, relative to the user's home. Read only by ``run_file``.
SQUADRON_RUNS_PARTS: Final = (".config", "squadron", "runs")


class AmoebaHomeError(Exception):
    """``AMOEBA_HOME`` is set to something that cannot name the home."""


def _override_home() -> Path | None:
    """``$AMOEBA_HOME`` as a path, ``None`` when unset.

    Raises:
        AmoebaHomeError: the variable is set but empty or relative. It never
            falls back to the default.
    """
    value = os.environ.get(HOME_VARIABLE)
    if value is None:
        return None
    if not value.strip():
        raise AmoebaHomeError(f"{HOME_VARIABLE} is set but empty")
    home = Path(value)
    if not home.is_absolute():
        raise AmoebaHomeError(
            f"{HOME_VARIABLE} must be an absolute path, got {value!r}"
        )
    return home


def config_home() -> Path:
    """The config home: ``$AMOEBA_HOME``, else ``~/.config/amoeba``.

    Resolved at every call, never at import, so a test can redirect it.

    Raises:
        AmoebaHomeError: the variable is set but empty or relative.
    """
    return _override_home() or Path.home().joinpath(*DEFAULT_CONFIG_HOME_PARTS)


def state_home() -> Path:
    """The state home: ``$AMOEBA_HOME``, else ``~/.local/state/amoeba``.

    Raises:
        AmoebaHomeError: the variable is set but empty or relative.
    """
    return _override_home() or Path.home().joinpath(*DEFAULT_STATE_HOME_PARTS)


def legacy_state_home() -> Path | None:
    """Where state lived before slice 228 (``~/.config/amoeba``), for the move.

    ``None`` when ``AMOEBA_HOME`` is set (both homes are then one directory) or
    when the legacy path equals the state home.

    Raises:
        AmoebaHomeError: the variable is set but empty or relative.
    """
    if _override_home() is not None:
        return None
    legacy = Path.home().joinpath(*DEFAULT_CONFIG_HOME_PARTS)
    return None if legacy == state_home() else legacy


def store_path() -> Path:
    """The SQLite store file under the state home."""
    return state_home() / STORE_FILE_NAME


def config_path() -> Path:
    """The user config file under the config home."""
    return config_home() / CONFIG_FILE_NAME


def answering_dir() -> Path:
    """Where each answering run's scratch directory lives, under the state home."""
    return state_home() / ANSWERING_DIR_NAME


def logs_dir() -> Path:
    """Where answering and resume logs live, under the state home."""
    return state_home() / LOGS_DIR_NAME


def calls_log_dir() -> Path:
    """Where the ``handle_pause`` calls log's day files live, under the logs."""
    return logs_dir() / CALLS_LOG_DIR_NAME


@dataclass(frozen=True)
class StateLayout:
    """Every state path, built once at the process boundary and passed down."""

    state_home: Path
    store_path: Path
    answering_dir: Path
    logs_dir: Path
    #: Where the ``handle_pause`` calls log's day files go (``calls_log_dir()``).
    calls_log_dir: Path
    #: The pre-228 home to move state out of, or ``None`` when there is none.
    legacy_home: Path | None


def state_layout() -> StateLayout:
    """The state paths for this process.

    Raises:
        AmoebaHomeError: ``AMOEBA_HOME`` is set but empty or relative.
    """
    return StateLayout(
        state_home=state_home(),
        store_path=store_path(),
        answering_dir=answering_dir(),
        logs_dir=logs_dir(),
        calls_log_dir=calls_log_dir(),
        legacy_home=legacy_state_home(),
    )


def squadron_runs_dir() -> Path:
    """Squadron's run-file directory, ``~/.config/squadron/runs``."""
    return Path.home().joinpath(*SQUADRON_RUNS_PARTS)
