"""The ``amoeba`` command (slices 222 to 229, D9, D13): the process boundary.

``main`` parses the arguments, runs the command's runner (``cli.commands``) and turns
the expected failures into an ``error: <ExceptionName>: <message>`` line on stderr and
an exit code. ``handle_pause`` also appends the calls-log line (228 D11). The exit
codes are defined in ``cli.exit_codes`` and re-exported here.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

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
from amoeba.cli.parser import build_parser
from amoeba.cli.registration_arguments import check_usage
from amoeba.config.home import StateLayout, state_layout
from amoeba.operations.names import OperationName
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
    name: OperationName = arguments.operation
    layout: StateLayout | None = None
    try:
        if name is OperationName.HANDLE_PAUSE:
            layout = state_layout()
            return run_handle_pause(layout, arguments.run_id, as_json=arguments.json)
        return run_invoked(name, arguments)
    except RequestDocumentError as error:
        sys.stderr.write(f"error: {type(error).__name__}: {error}\n")
        return EXIT_USAGE
    except OPERATIONAL_ERRORS as error:
        # The process boundary: these are the expected failures, reported once. With
        # no layout (no state home) there is no calls log to write: stderr only.
        sys.stderr.write(f"error: {type(error).__name__}: {error}\n")
        if name is OperationName.HANDLE_PAUSE and layout is not None:
            log_failed_call(layout, arguments.run_id, error)
        return EXIT_ERROR
