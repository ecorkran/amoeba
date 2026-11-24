"""``amoeba wake-run WAKE_ID``: the wake wrapper's command line (slice 244, D6).

An internal, CLI-only command, started by Amoeba when a request wakes a member and not
meant for people. It is no ``OperationName``, has no MCP tool and prints no result: the
command's own output is the wake's log. It loads no config (the deadline is in the
row), so a live store whose config is missing a key does not stop a wrapper that is
already starting.
"""

from __future__ import annotations

import argparse
from typing import Any, Final

from amoeba.cli.answer_first_install import ANSWER_FIRST_COMMAND
from amoeba.cli.exit_codes import EXIT_ERROR, EXIT_OK, EXIT_REJECTED
from amoeba.cli.hub_commands import HUB_COMMAND
from amoeba.cli.init_command import INIT_COMMAND
from amoeba.cli.join_command import JOIN_COMMAND, LEAVE_COMMAND
from amoeba.cli.stand_in_command import STAND_IN_COMMAND
from amoeba.config.home import StateLayout
from amoeba.operations.wake_run import WAKE_RUN_COMMAND, run_wake
from amoeba.store.vocabulary import WakeOutcome
from amoeba.wiring import default_deps, open_store

#: Commands that are not operations: no ``OperationName`` and no tool.
CLI_ONLY_COMMANDS: Final = frozenset(
    {
        WAKE_RUN_COMMAND,
        STAND_IN_COMMAND,
        ANSWER_FIRST_COMMAND,
        INIT_COMMAND,
        JOIN_COMMAND,
        LEAVE_COMMAND,
        HUB_COMMAND,
    }
)

#: The exit code of each way a wake is recorded (D6): the command's own exit code is
#: data, a start failure is 1, and the wrapper's own unexpected error is operational.
WAKE_EXIT_CODES: Final = {
    WakeOutcome.EXITED: EXIT_OK,
    WakeOutcome.TIMED_OUT: EXIT_OK,
    WakeOutcome.START_FAILED: EXIT_REJECTED,
    WakeOutcome.WRAPPER_FAILED: EXIT_ERROR,
    # Set by ``rm-machine``, never by a wrapper; mapped so the table is total.
    WakeOutcome.MACHINE_REMOVED: EXIT_ERROR,
}


def register_wake_run(commands: Any) -> argparse.ArgumentParser:
    parser = commands.add_parser(
        WAKE_RUN_COMMAND,
        help="internal: run one wake's command (started by Amoeba, not for people)",
    )
    parser.set_defaults(cli_only=WAKE_RUN_COMMAND)
    parser.add_argument("wake_id", help="the wake's id, from its row")
    return parser


def run_wake_run(layout: StateLayout, wake_id: str) -> int:
    """Run the wake and return the exit code for how it was recorded.

    Raises:
        WakeRunError: The row is missing or already ended.
        StoreError: The store cannot be used.
    """
    deps = default_deps(layout)
    with open_store(layout) as store:
        outcome = run_wake(store, deps, wake_id)
    return WAKE_EXIT_CODES[outcome]
