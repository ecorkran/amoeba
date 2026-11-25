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

A development build (an editable install, as ``uv sync`` makes in the checkout) has
its own homes, ``~/.config/amoeba-dev`` and ``~/.local/state/amoeba-dev``, so trying
unreleased code, its migrations included, never touches the installed amoeba's store.
Only ``scripts/update_live.py`` reaches the installed homes from the checkout, through
``installed_config_home`` and ``installed_state_home``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import cache
from importlib import metadata
from pathlib import Path
from typing import Final

#: The variable that redirects both homes, read at call time (222 D1, 228 D1).
HOME_VARIABLE: Final = "AMOEBA_HOME"
#: Where the config home is when the variable is unset, relative to the user's home.
DEFAULT_CONFIG_HOME_PARTS: Final = (".config", "amoeba")
#: Where the state home is when the variable is unset, relative to the user's home.
DEFAULT_STATE_HOME_PARTS: Final = (".local", "state", "amoeba")
#: Added to the last part of each default home for a development build.
DEV_HOME_SUFFIX: Final = "-dev"
#: The distribution whose install record says whether this is a development build.
PACKAGE_NAME: Final = "amoeba-ai"
#: The install record PEP 610 defines; an editable install says so in ``dir_info``.
DIRECT_URL_FILE_NAME: Final = "direct_url.json"
STORE_FILE_NAME: Final = "amoeba.sqlite3"
CONFIG_FILE_NAME: Final = "config.yaml"
#: The client file `amoeba join` writes (config home): address, machine, token (260 D1).
CLIENT_FILE_NAME: Final = "client.yaml"
#: The hub's own config (config home). A home holding it is a hub's home (260 D1).
HUB_FILE_NAME: Final = "hub.yaml"
#: The hub certificate a client saved at `join` (client state home).
PINNED_CERT_FILE_NAME: Final = "pinned-hub-cert.pem"
#: The hub's own certificate and key (hub state home).
HUB_CERT_FILE_NAME: Final = "hub-cert.pem"
HUB_KEY_FILE_NAME: Final = "hub-key.pem"
#: The hub's rotating log: ``<logs>/hub/hub.log``.
HUB_LOG_DIR_NAME: Final = "hub"
HUB_LOG_FILE_NAME: Final = "hub.log"
#: Scratch directories of answering runs, one per run id (slice 223, D12).
ANSWERING_DIR_NAME: Final = "answering"
#: Stdout and stderr logs of answering runs and resumes.
LOGS_DIR_NAME: Final = "logs"
#: One JSONL file per UTC day of ``handle_pause`` calls, under the logs (228 D11).
CALLS_LOG_DIR_NAME: Final = "calls"
#: Squadron's run files, relative to the user's home. Read only by ``run_file``.
SQUADRON_RUNS_PARTS: Final = (".config", "squadron", "runs")
CLAUDE_HOME_PARTS: Final = (".claude",)


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


def is_editable_record(direct_url: str | None) -> bool:
    """Whether a ``direct_url.json`` text records an editable install.

    ``None`` (no record) is an install from an index, such as ``uv tool install``.
    """
    if direct_url is None:
        return False
    dir_info = json.loads(direct_url).get("dir_info", {})
    return dir_info.get("editable") is True


@cache
def is_dev_build() -> bool:
    """Whether this process runs a development build (an editable install)."""
    record = metadata.distribution(PACKAGE_NAME).read_text(DIRECT_URL_FILE_NAME)
    return is_editable_record(record)


def _default_home(parts: tuple[str, ...], *, dev: bool) -> Path:
    if dev:
        parts = (*parts[:-1], parts[-1] + DEV_HOME_SUFFIX)
    return Path.home().joinpath(*parts)


def config_home() -> Path:
    """The config home: ``$AMOEBA_HOME``, else ``~/.config/amoeba`` (``amoeba-dev``
    for a development build).

    Resolved at every call, never at import, so a test can redirect it.

    Raises:
        AmoebaHomeError: the variable is set but empty or relative.
    """
    return _override_home() or _default_home(
        DEFAULT_CONFIG_HOME_PARTS, dev=is_dev_build()
    )


def state_home() -> Path:
    """The state home: ``$AMOEBA_HOME``, else ``~/.local/state/amoeba``
    (``amoeba-dev`` for a development build).

    Raises:
        AmoebaHomeError: the variable is set but empty or relative.
    """
    return _override_home() or _default_home(
        DEFAULT_STATE_HOME_PARTS, dev=is_dev_build()
    )


def installed_config_home() -> Path:
    """The installed amoeba's config home, whatever build asks: for
    ``scripts/update_live.py``, which runs from the checkout.

    Raises:
        AmoebaHomeError: the variable is set but empty or relative.
    """
    return _override_home() or _default_home(DEFAULT_CONFIG_HOME_PARTS, dev=False)


def installed_state_home() -> Path:
    """The installed amoeba's state home, whatever build asks.

    Raises:
        AmoebaHomeError: the variable is set but empty or relative.
    """
    return _override_home() or _default_home(DEFAULT_STATE_HOME_PARTS, dev=False)


def legacy_state_home() -> Path | None:
    """Where state lived before slice 228 (``~/.config/amoeba``), for the move.

    ``None`` when ``AMOEBA_HOME`` is set (both homes are then one directory), for a
    development build (its homes are newer than the move), or when the legacy path
    equals the state home.

    Raises:
        AmoebaHomeError: the variable is set but empty or relative.
    """
    if _override_home() is not None or is_dev_build():
        return None
    legacy = Path.home().joinpath(*DEFAULT_CONFIG_HOME_PARTS)
    return None if legacy == state_home() else legacy


def store_path() -> Path:
    """The SQLite store file under the state home."""
    return state_home() / STORE_FILE_NAME


def config_path() -> Path:
    """The user config file under the config home."""
    return config_home() / CONFIG_FILE_NAME


def client_file_path() -> Path:
    """The client file under the config home."""
    return config_home() / CLIENT_FILE_NAME


def hub_file_path() -> Path:
    """The hub's ``hub.yaml`` under the config home."""
    return config_home() / HUB_FILE_NAME


def pinned_cert_path() -> Path:
    """The saved hub certificate under the (client's) state home."""
    return state_home() / PINNED_CERT_FILE_NAME


def hub_cert_path() -> Path:
    """The hub's certificate under its state home."""
    return state_home() / HUB_CERT_FILE_NAME


def hub_key_path() -> Path:
    """The hub's private key under its state home."""
    return state_home() / HUB_KEY_FILE_NAME


def hub_log_path() -> Path:
    """The hub's log file, under the logs directory."""
    return logs_dir() / HUB_LOG_DIR_NAME / HUB_LOG_FILE_NAME


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
    #: The client file (config home): its presence means this machine is joined.
    client_file: Path
    #: ``hub.yaml`` (config home): its presence makes this home a hub's.
    hub_file: Path
    #: The hub certificate saved at `join` (state home).
    pinned_cert: Path
    #: The hub's certificate and key (state home), and its log file.
    hub_cert: Path
    hub_key: Path
    hub_log: Path


def layout_under(state: Path, config: Path, legacy_home: Path | None) -> StateLayout:
    """The layout of a state home and a config home. ``state_layout()`` builds the
    process's from the environment; a test builds one under its own directories."""
    logs = state / LOGS_DIR_NAME
    return StateLayout(
        state_home=state,
        store_path=state / STORE_FILE_NAME,
        answering_dir=state / ANSWERING_DIR_NAME,
        logs_dir=logs,
        calls_log_dir=logs / CALLS_LOG_DIR_NAME,
        legacy_home=legacy_home,
        client_file=config / CLIENT_FILE_NAME,
        hub_file=config / HUB_FILE_NAME,
        pinned_cert=state / PINNED_CERT_FILE_NAME,
        hub_cert=state / HUB_CERT_FILE_NAME,
        hub_key=state / HUB_KEY_FILE_NAME,
        hub_log=logs / HUB_LOG_DIR_NAME / HUB_LOG_FILE_NAME,
    )


def state_layout() -> StateLayout:
    """The state paths for this process.

    Raises:
        AmoebaHomeError: ``AMOEBA_HOME`` is set but empty or relative.
    """
    return layout_under(state_home(), config_home(), legacy_state_home())


def squadron_runs_dir() -> Path:
    """Squadron's run-file directory, ``~/.config/squadron/runs``."""
    return Path.home().joinpath(*SQUADRON_RUNS_PARTS)


def user_home() -> Path:
    """The user's home directory: where the stand-in stops walking up for rules."""
    return Path.home()


def claude_home() -> Path:
    """Claude Code's user directory, ``~/.claude``: global rules and session memory."""
    return Path.home().joinpath(*CLAUDE_HOME_PARTS)
