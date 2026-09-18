"""Resolution of the central, per-supervisor store path.

The store is central and project-keyed, per the slice 101 design: one store per
supervisor under ``~/.config/amoeba/``, matching Squadron's
``~/.config/squadron/``. There is deliberately no per-project override.

Resolution is a pure computation. Nothing here touches the filesystem; the
store's open path (``store.py``) is what creates directories.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Environment variable that overrides the store directory outright. Highest
#: precedence — set it and neither XDG nor the default is consulted.
STORE_DIR_ENV_VAR = "AMOEBA_STORE_DIR"

#: XDG base-directory variable consulted when the override is unset.
XDG_CONFIG_HOME_ENV_VAR = "XDG_CONFIG_HOME"

#: Directory name under the XDG config root (or under ``~/.config``) holding
#: Amoeba's stores. Referenced rather than repeated as a literal.
STORE_DIR_NAME = "amoeba"

#: The default store directory when neither the override nor XDG is set.
DEFAULT_STORE_DIR = Path.home() / ".config" / STORE_DIR_NAME

#: Filename suffix for a project's store file.
STORE_FILE_SUFFIX = ".sqlite3"


def store_dir(env: dict[str, str] | None = None) -> Path:
    """Resolve the directory holding this supervisor's stores.

    Precedence, highest first:

    1. ``AMOEBA_STORE_DIR`` — used verbatim.
    2. ``XDG_CONFIG_HOME`` — yields ``$XDG_CONFIG_HOME/amoeba``.
    3. ``DEFAULT_STORE_DIR`` — ``~/.config/amoeba``.

    Args:
        env: Environment mapping to read. Defaults to ``os.environ``. Present so
            tests can supply an environment without mutating the process.

    Returns:
        The resolved directory. It is not created and may not exist.
    """
    environment = os.environ if env is None else env

    override = environment.get(STORE_DIR_ENV_VAR)
    if override:
        return Path(override)

    xdg_config_home = environment.get(XDG_CONFIG_HOME_ENV_VAR)
    if xdg_config_home:
        return Path(xdg_config_home) / STORE_DIR_NAME

    return DEFAULT_STORE_DIR


def store_path(project_id: str, env: dict[str, str] | None = None) -> Path:
    """Resolve the store file path for a project.

    The store is central and keyed by project: every project's nodes live in a
    file named for that project under the resolved store directory.

    Args:
        project_id: The project scope key. Must be non-empty.
        env: Environment mapping to read. Defaults to ``os.environ``.

    Returns:
        The resolved file path. It is not created and may not exist.

    Raises:
        ValueError: If ``project_id`` is empty or contains a path separator,
            which would let a project id escape the store directory.
    """
    if not project_id:
        raise ValueError("project_id must be non-empty")
    if os.sep in project_id or (os.altsep is not None and os.altsep in project_id):
        raise ValueError(
            f"project_id must not contain a path separator: {project_id!r}"
        )
    if project_id in {os.curdir, os.pardir}:
        raise ValueError(f"project_id must not be a path component: {project_id!r}")

    return store_dir(env) / f"{project_id}{STORE_FILE_SUFFIX}"
