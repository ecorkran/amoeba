"""The ``amoeba`` command (slices 222 to 229, D9, D13): the process boundary.

``main`` parses the arguments, runs the command's runner (``cli.commands``) and turns
the expected failures into an ``error: <ExceptionName>: <message>`` line on stderr and
an exit code. ``handle_pause`` also appends the calls-log line (228 D11). The exit
codes are defined in ``cli.exit_codes`` and re-exported here. At a terminal the
library's log records are message lines with no traceback (``cli.terminal_log``).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from amoeba.cli.answer_first_install import (
    ANSWER_FIRST_COMMAND,
    AnswerFirstInstallError,
    run_answer_first_install,
)
from amoeba.cli.commands import (
    RequestDocumentError,
    log_failed_call,
    run_handle_pause,
    run_invoked,
)
from amoeba.cli.exit_codes import (
    EXIT_ERROR,
    EXIT_OK,
    EXIT_REJECTED,
    EXIT_USAGE,
)
from amoeba.cli.hub_commands import ACTION, HUB_COMMAND, SERVE, run_hub
from amoeba.cli.init_command import INIT_COMMAND, run_init
from amoeba.cli.join_command import JOIN_COMMAND, LEAVE_COMMAND, run_join, run_leave
from amoeba.cli.parser import build_parser
from amoeba.cli.registration_arguments import check_usage
from amoeba.cli.resume_command import run_resume_run
from amoeba.cli.stand_in_command import STAND_IN_COMMAND, run_stand_in
from amoeba.cli.terminal_log import terminal_log
from amoeba.cli.wake_command import run_wake_run
from amoeba.config.home import StateLayout, state_layout
from amoeba.hub.backups import BackupError
from amoeba.hub.errors import HubStartError
from amoeba.operations.names import OperationName
from amoeba.operations.resume_run import RESUME_RUN_COMMAND
from amoeba.operations.wake_run import WAKE_RUN_COMMAND, WakeRunError
from amoeba.wiring import OPERATIONAL_ERRORS

__all__ = [
    "EXIT_ERROR",
    "EXIT_OK",
    "EXIT_REJECTED",
    "EXIT_USAGE",
    "main",
]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command; returns the exit code."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    check_usage(parser, arguments)
    if _serves_a_hub(arguments):
        # The serving process logs to its rotating file and nowhere else (260 D16).
        return _run(parser, arguments)
    with terminal_log(sys.stderr):
        return _run(parser, arguments)


def _serves_a_hub(arguments: argparse.Namespace) -> bool:
    return (
        getattr(arguments, "cli_only", None) == HUB_COMMAND
        and getattr(arguments, ACTION) == SERVE
    )


def _run(parser: argparse.ArgumentParser, arguments: argparse.Namespace) -> int:
    """Run the parsed command and report its expected failures."""
    layout: StateLayout | None = None
    # A CLI-only command (``wake-run``) sets no operation.
    name: OperationName | None = getattr(arguments, "operation", None)
    try:
        if getattr(arguments, "cli_only", None) == STAND_IN_COMMAND:
            # The end-of-turn hook: never touches the calls log or an operation.
            return run_stand_in()
        if getattr(arguments, "cli_only", None) == ANSWER_FIRST_COMMAND:
            # Edits Claude Code's settings only: no state home, no operation.
            return run_answer_first_install(arguments.action)
        if getattr(arguments, "cli_only", None) == INIT_COMMAND:
            # Sets the machine up: must run before any config load, which would fail.
            return run_init()
        if getattr(arguments, "cli_only", None) == WAKE_RUN_COMMAND:
            return run_wake_run(state_layout(), arguments.wake_id)
        if getattr(arguments, "cli_only", None) == RESUME_RUN_COMMAND:
            # Started by the after-step with a claim; runs no after-step of its own.
            return run_resume_run(
                state_layout(), arguments.answer_seq, arguments.claim_id
            )
        if getattr(arguments, "cli_only", None) == HUB_COMMAND:
            return run_hub(arguments)
        if getattr(arguments, "cli_only", None) == JOIN_COMMAND:
            return run_join(parser, arguments)
        if getattr(arguments, "cli_only", None) == LEAVE_COMMAND:
            return run_leave(arguments)
        if name is None:
            raise AssertionError("a parsed command is an operation or CLI-only")
        if name is OperationName.HANDLE_PAUSE:
            layout = state_layout()
            return run_handle_pause(layout, arguments.run_id, as_json=arguments.json)
        return run_invoked(name, arguments)
    except RequestDocumentError as error:
        sys.stderr.write(f"error: {type(error).__name__}: {error}\n")
        return EXIT_USAGE
    except (
        AnswerFirstInstallError,
        WakeRunError,
        HubStartError,
        BackupError,
        *OPERATIONAL_ERRORS,
    ) as error:
        # The process boundary: these are the expected failures, reported once. With
        # no layout (no state home) there is no calls log to write: stderr only.
        sys.stderr.write(f"error: {type(error).__name__}: {error}\n")
        if name is OperationName.HANDLE_PAUSE and layout is not None:
            log_failed_call(layout, arguments.run_id, error)
        return EXIT_ERROR
