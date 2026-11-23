"""``amoeba init``: take a machine from nothing to a working Amoeba.

It writes the starter config when there is none, adds the keys an older config lacks,
and creates the store. It is safe to repeat: a machine that is already set up is left
exactly as it is, and the command says so. It never overwrites a value a person set.

A CLI-only command: no ``OperationName`` and no MCP tool, since it sets up the machine
of the person at the keyboard.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Final

from amoeba.cli.exit_codes import EXIT_OK
from amoeba.config.home import config_path, state_layout, store_path
from amoeba.config.starter import fill_missing_keys, starter_values, write_starter
from amoeba.wiring import open_store

INIT_COMMAND: Final = "init"


def register_init(commands: Any) -> argparse.ArgumentParser:
    parser = commands.add_parser(
        INIT_COMMAND,
        help="set this machine up: write the starter config and create the store",
    )
    parser.set_defaults(cli_only=INIT_COMMAND)
    return parser


def _set_up_config() -> str:
    """Write or complete the config; the line that says what was done."""
    path = config_path()
    if not path.exists():
        write_starter(path)
        return (
            f"config: wrote {path}\n"
            "  answer_model and check_model are placeholders; set them to Squadron "
            "model aliases before Amoeba answers a paused pipeline run\n"
        )
    added = fill_missing_keys(path, starter_values())
    if added:
        return f"config: added {', '.join(added)} to {path}\n"
    return f"config: {path} is already complete\n"


def _set_up_store() -> str:
    """Create the store, or bring an existing one up to date; the line saying which."""
    existed = store_path().exists()
    with open_store(state_layout()):
        pass  # opening creates the file and applies any migration it lacks
    state = "is already there" if existed else "created"
    return f"store: {store_path()} {state}\n"


def run_init() -> int:
    """Set the machine up; the process exit code.

    Raises:
        ConfigError: An existing config has a fault that adding keys does not fix.
        AmoebaHomeError, StoreError: The home or the store cannot be used.
    """
    sys.stdout.write(_set_up_config())
    sys.stdout.write(_set_up_store())
    sys.stdout.write("next: run `amoeba add` in a repo to register it\n")
    return EXIT_OK
