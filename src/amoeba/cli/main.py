"""The ``amoeba`` command (slices 222 and 223, D9, D13): one subcommand per operation.

This is the process boundary. It alone calls ``amoeba_home()``, ``store_path()`` and
``config_path()``, reads the request text, and turns the expected failures into an
``error: <ExceptionName>: <message>`` line on stderr and an exit code. Later slices
add subcommands and reuse the exit codes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Final

import yaml

from amoeba.config.home import (
    AmoebaHomeError,
    answering_dir,
    config_path,
    logs_dir,
    squadron_runs_dir,
    store_path,
)
from amoeba.config.user_config import ConfigError, load_user_config
from amoeba.operations.answer import AnswerOutcome, answer
from amoeba.operations.deps import Deps, production_deps
from amoeba.operations.handle_pause import handle_pause
from amoeba.operations.members import ContextForgeError
from amoeba.operations.set_up import set_up
from amoeba.operations.set_up_models import SetUpOutcome
from amoeba.store.errors import StoreError
from amoeba.store.store import Store
from amoeba.upstream.squadron.errors import SquadronError

#: Exit codes, shared by every subcommand.
EXIT_OK: Final = 0  # the operation succeeded (for set_up: applied or unchanged)
EXIT_REJECTED: Final = 1  # the operation refused the request; the result says why
EXIT_USAGE: Final = 2  # bad arguments, or a request that cannot be read
EXIT_ERROR: Final = 3  # config, home, Context Forge or store failure

SET_UP_COMMAND: Final = "set_up"
HANDLE_PAUSE_COMMAND: Final = "handle_pause"
ANSWER_COMMAND: Final = "answer"
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


def _run_set_up(source: str) -> int:
    document = read_request_document(source)
    config = load_user_config(config_path())
    with Store.open(store_path()) as store:
        result = set_up(
            store, config, document, directory=Path.cwd(), run=subprocess.run
        )
    sys.stdout.write(result.model_dump_json(indent=JSON_INDENT) + "\n")
    return EXIT_REJECTED if result.outcome is SetUpOutcome.REJECTED else EXIT_OK


def _deps() -> Deps:
    """The real edges, with the home's directories; only the CLI asks the home."""
    return production_deps(
        answering_dir=answering_dir(),
        logs_dir=logs_dir(),
        squadron_runs_dir=squadron_runs_dir(),
    )


def _print_result(result: object) -> None:
    """A dataclass result as JSON on stdout (enums are strings)."""
    if not is_dataclass(result) or isinstance(result, type):
        raise TypeError(f"not a result value: {result!r}")
    sys.stdout.write(json.dumps(asdict(result), indent=JSON_INDENT) + "\n")


def _run_handle_pause(run_id: str) -> int:
    config = load_user_config(config_path())
    deps = _deps()
    with Store.open(store_path()) as store:
        result = handle_pause(store, config, run_id, directory=Path.cwd(), deps=deps)
    _print_result(result)
    return EXIT_OK


def _run_answer(run_id: str, paused_at: str | None, text: str) -> int:
    config = load_user_config(config_path())
    deps = _deps()
    document: dict[str, str] = {"run_id": run_id, "text": text}
    if paused_at is not None:
        document["paused_at"] = paused_at
    with Store.open(store_path()) as store:
        result = answer(store, config, document, deps=deps)
    _print_result(result)
    return EXIT_REJECTED if result.outcome is AnswerOutcome.REJECTED else EXIT_OK


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="amoeba", description="Amoeba: the program tool."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    set_up_parser = commands.add_parser(
        SET_UP_COMMAND,
        help="register or update a program, its members and dependencies",
    )
    set_up_parser.add_argument(
        "--file",
        required=True,
        metavar="PATH",
        help=f"the request document (YAML); {STDIN_SOURCE} reads standard input",
    )
    pause_parser = commands.add_parser(
        HANDLE_PAUSE_COMMAND,
        help="answer a paused run's question and resume it, or record it as waiting",
    )
    pause_parser.add_argument("run_id", help="the paused run (run in its checkout)")
    answer_parser = commands.add_parser(
        ANSWER_COMMAND, help="record the PM's answer to a question, then resume the run"
    )
    answer_parser.add_argument("run_id", help="the run the question was asked in")
    answer_parser.add_argument(
        "--paused-at",
        metavar="TIMESTAMP",
        help="the pause, as `sq runs wait --json` prints it (default: the latest)",
    )
    answer_parser.add_argument("--text", required=True, help="the answer")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command; returns the exit code."""
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == SET_UP_COMMAND:
            return _run_set_up(arguments.file)
        if arguments.command == HANDLE_PAUSE_COMMAND:
            return _run_handle_pause(arguments.run_id)
        if arguments.command == ANSWER_COMMAND:
            return _run_answer(arguments.run_id, arguments.paused_at, arguments.text)
        raise AssertionError(f"unhandled command {arguments.command!r}")
    except RequestDocumentError as error:
        sys.stderr.write(f"error: {type(error).__name__}: {error}\n")
        return EXIT_USAGE
    except (
        ConfigError,
        AmoebaHomeError,
        ContextForgeError,
        SquadronError,
        StoreError,
    ) as error:
        # The process boundary: these are the expected failures, reported once.
        sys.stderr.write(f"error: {type(error).__name__}: {error}\n")
        return EXIT_ERROR
