"""The ``amoeba`` command (slices 222 to 224, D9, D13): one subcommand per operation.

This is the process boundary of the command-line door. It reads the request text,
builds each operation's document, hands it to ``wiring.invoke`` (which places every
argument), and turns the expected failures into an ``error: <ExceptionName>:
<message>`` line on stderr and an exit code. ``handle_pause`` keeps its own body: it
also appends the calls-log line (228 D11). Later slices add subcommands and reuse the
exit codes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import yaml

from amoeba.config.home import StateLayout, state_layout
from amoeba.operations.calls_log import append_call, error_entry, result_entry
from amoeba.operations.handle_pause import handle_pause
from amoeba.operations.names import Door, OperationName
from amoeba.wiring import (
    OPERATIONAL_ERRORS,
    OperationResult,
    default_deps,
    invoke,
    is_rejected,
    load_config,
    open_store,
    result_document,
)

#: Exit codes, shared by every subcommand.
EXIT_OK: Final = 0  # the operation succeeded (for set_up: applied or unchanged)
EXIT_REJECTED: Final = 1  # the operation refused the request; the result says why
EXIT_USAGE: Final = 2  # bad arguments, or a request that cannot be read
EXIT_ERROR: Final = 3  # config, home, Context Forge or store failure

STDIN_SOURCE: Final = "-"
STDIN_NAME: Final = "<stdin>"
JSON_INDENT: Final = 2


class RequestDocumentError(Exception):
    """The request cannot be read, is not UTF-8, or is not YAML; names the source."""


def read_request_document(source: str) -> object:
    """The parsed YAML of the file at ``source``, or of stdin when it is ``-``.

    A document that parses but has the wrong shape is returned as is; the operation
    reports it as ``malformed``.

    Raises:
        RequestDocumentError: Unreadable, not UTF-8 or not YAML.
    """
    name = STDIN_NAME if source == STDIN_SOURCE else source
    try:
        raw = (
            sys.stdin.buffer.read()
            if source == STDIN_SOURCE
            else Path(source).read_bytes()
        )
    except OSError as error:
        raise RequestDocumentError(f"{name}: cannot read: {error}") from error
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RequestDocumentError(f"{name}: not UTF-8: {error}") from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise RequestDocumentError(f"{name}: not YAML: {error}") from error


def _print_json(document: object) -> None:
    """A JSON document on stdout."""
    sys.stdout.write(json.dumps(document, indent=JSON_INDENT, ensure_ascii=False))
    sys.stdout.write("\n")


def _with_optional(
    document: dict[str, object], **optional: object
) -> dict[str, object]:
    """``document`` plus each optional value that was given."""
    return {**document, **{k: v for k, v in optional.items() if v is not None}}


def _document_for(name: OperationName, arguments: argparse.Namespace) -> object:
    """The request document an in-process operation is given, from its arguments."""
    match name:
        case OperationName.SET_UP:
            return read_request_document(arguments.file)
        case OperationName.ANSWER:
            return _with_optional(
                {"run_id": arguments.run_id, "text": arguments.text},
                paused_at=arguments.paused_at,
            )
        case OperationName.STATUS:
            return _with_optional({}, program=arguments.program)
        case OperationName.DECISIONS:
            return _with_optional({}, since=arguments.since, program=arguments.program)
        case OperationName.MARK_READ:
            return {"through": arguments.through}
        case OperationName.DISMISS:
            return _with_optional(
                {"run_id": arguments.run_id, "reason": arguments.reason},
                paused_at=arguments.paused_at,
            )
        case OperationName.RETRACT:
            return {"answer_seq": arguments.answer_seq, "reason": arguments.reason}
        case OperationName.HANDLE_PAUSE:
            raise ValueError(f"{name.value} has no request document")


def _run_invoked(name: OperationName, arguments: argparse.Namespace) -> int:
    """Run an in-process operation through ``wiring.invoke``; print its result."""
    result: OperationResult = invoke(
        name, _document_for(name, arguments), Path.cwd(), Door.CLI
    )
    _print_json(result_document(result))
    return EXIT_REJECTED if is_rejected(result) else EXIT_OK


def _run_handle_pause(layout: StateLayout, run_id: str) -> int:
    config = load_config()
    deps = default_deps(layout)
    directory = Path.cwd()
    with open_store(layout) as store:
        result = handle_pause(store, config, run_id, directory=directory, deps=deps)
    _print_json(asdict(result))
    # After the result is printed: a log failure cannot change what was reported.
    now = deps.clock()
    reason = result.skip_reason or result.waiting_reason
    entry = result_entry(run_id, directory, result.outcome, reason, result.detail, now)
    append_call(layout.calls_log_dir, entry, now)
    return EXIT_OK


def _log_failed_call(layout: StateLayout, run_id: str, error: Exception) -> None:
    """The calls-log line of a ``handle_pause`` that ended in an exit-3 error."""
    now = datetime.now(UTC)
    entry = error_entry(run_id, Path.cwd(), error, now)
    append_call(layout.calls_log_dir, entry, now)


def _add_paused_at(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--paused-at",
        metavar="TIMESTAMP",
        help="the pause, as `sq runs wait --json` prints it (default: the latest)",
    )


def build_parser() -> argparse.ArgumentParser:
    """The command's parser; one subcommand per ``OperationName``."""
    parser = argparse.ArgumentParser(
        prog="amoeba", description="Amoeba: the program tool."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    set_up_parser = commands.add_parser(
        OperationName.SET_UP.value,
        help="register or update a program, its members and dependencies",
    )
    set_up_parser.add_argument(
        "--file",
        required=True,
        metavar="PATH",
        help=f"the request document (YAML); {STDIN_SOURCE} reads standard input",
    )
    pause_parser = commands.add_parser(
        OperationName.HANDLE_PAUSE.value,
        help="answer a paused run's question and resume it, or record it as waiting",
    )
    pause_parser.add_argument("run_id", help="the paused run (run in its checkout)")
    answer_parser = commands.add_parser(
        OperationName.ANSWER.value,
        help="record the PM's answer to a question, then resume the run",
    )
    answer_parser.add_argument("run_id", help="the run the question was asked in")
    _add_paused_at(answer_parser)
    answer_parser.add_argument("--text", required=True, help="the answer")
    status_parser = commands.add_parser(
        OperationName.STATUS.value,
        help="runs, pauses and questions waiting on the PM, per program and member",
    )
    status_parser.add_argument(
        "--program", metavar="ID", help="only this program (default: see the contract)"
    )
    decisions_parser = commands.add_parser(
        OperationName.DECISIONS.value,
        help="answers recorded since the PM's marker, or since a time",
    )
    decisions_parser.add_argument(
        "--since",
        metavar="ISO-8601",
        help="start at this time, with a UTC offset (default: after the marker)",
    )
    decisions_parser.add_argument("--program", metavar="ID", help="only this program")
    mark_read_parser = commands.add_parser(
        OperationName.MARK_READ.value,
        help="move the PM's marker forward to the last record seen",
    )
    mark_read_parser.add_argument(
        "--through",
        required=True,
        type=int,
        metavar="SEQ",
        help="the read_through of a decisions call",
    )
    dismiss_parser = commands.add_parser(
        OperationName.DISMISS.value,
        help="close a question that has no answer to deliver; the run stays paused",
    )
    dismiss_parser.add_argument("run_id", help="the run the question was asked in")
    _add_paused_at(dismiss_parser)
    dismiss_parser.add_argument("--reason", required=True, help="why it is closed")
    retract_parser = commands.add_parser(
        OperationName.RETRACT.value,
        help="stop a PM answer being precedent; it stays delivered and listed",
    )
    retract_parser.add_argument(
        "answer_seq", type=int, help="the answer's seq, from `amoeba decisions`"
    )
    retract_parser.add_argument("--reason", required=True, help="why it is retracted")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command; returns the exit code."""
    arguments = build_parser().parse_args(argv)
    name = OperationName(arguments.command)
    layout: StateLayout | None = None
    try:
        if name is OperationName.HANDLE_PAUSE:
            layout = state_layout()
            return _run_handle_pause(layout, arguments.run_id)
        return _run_invoked(name, arguments)
    except RequestDocumentError as error:
        sys.stderr.write(f"error: {type(error).__name__}: {error}\n")
        return EXIT_USAGE
    except OPERATIONAL_ERRORS as error:
        # The process boundary: these are the expected failures, reported once. With
        # no layout (no state home) there is no calls log to write: stderr only.
        sys.stderr.write(f"error: {type(error).__name__}: {error}\n")
        if name is OperationName.HANDLE_PAUSE and layout is not None:
            _log_failed_call(layout, arguments.run_id, error)
        return EXIT_ERROR
