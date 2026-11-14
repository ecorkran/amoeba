"""The ``amoeba`` argument parser (slices 222 to 229): one subcommand per operation.

Each command is registered under its ``OperationName.cli_name`` (``handle-pause``,
``mark-read``); an old underscore name is no alias, so it gets argparse's
invalid-choice error and exit 2. Every command takes ``-j``/``--json`` after its name,
through one parent parser. A subparser records its operation as ``operation``.
"""

from __future__ import annotations

import argparse
from typing import Any

from amoeba.cli.registration_arguments import (
    register_add,
    register_list,
    register_rm,
)
from amoeba.operations.names import OperationName


def _json_parent() -> argparse.ArgumentParser:
    """The parent parser that gives every command ``-j``/``--json``."""
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="print the result as JSON instead of text",
    )
    return parent


def _command(
    commands: Any, json_parent: argparse.ArgumentParser, name: OperationName, help: str
) -> argparse.ArgumentParser:
    parser = commands.add_parser(name.cli_name, parents=[json_parent], help=help)
    parser.set_defaults(operation=name)
    return parser


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
    parent = _json_parent()
    register_add(commands, parent)
    register_rm(commands, parent)
    register_list(commands, parent)
    pause_parser = _command(
        commands,
        parent,
        OperationName.HANDLE_PAUSE,
        "answer a paused run's question and resume it, or record it as waiting",
    )
    pause_parser.add_argument("run_id", help="the paused run (run in its checkout)")
    answer_parser = _command(
        commands,
        parent,
        OperationName.ANSWER,
        "record the PM's answer to a question, then resume the run",
    )
    answer_parser.add_argument("run_id", help="the run the question was asked in")
    _add_paused_at(answer_parser)
    answer_parser.add_argument("--text", required=True, help="the answer")
    status_parser = _command(
        commands,
        parent,
        OperationName.STATUS,
        "runs, pauses and questions waiting on the PM, per program and member",
    )
    status_parser.add_argument(
        "--program", metavar="ID", help="only this program (default: see the contract)"
    )
    decisions_parser = _command(
        commands,
        parent,
        OperationName.DECISIONS,
        "answers recorded since the PM's marker, or since a time",
    )
    decisions_parser.add_argument(
        "--since",
        metavar="ISO-8601",
        help="start at this time, with a UTC offset (default: after the marker)",
    )
    decisions_parser.add_argument("--program", metavar="ID", help="only this program")
    mark_read_parser = _command(
        commands,
        parent,
        OperationName.MARK_READ,
        "move the PM's marker forward to the last record seen",
    )
    mark_read_parser.add_argument(
        "--through",
        required=True,
        type=int,
        metavar="SEQ",
        help="the read_through of a decisions call",
    )
    dismiss_parser = _command(
        commands,
        parent,
        OperationName.DISMISS,
        "close a question that has no answer to deliver; the run stays paused",
    )
    dismiss_parser.add_argument("run_id", help="the run the question was asked in")
    _add_paused_at(dismiss_parser)
    dismiss_parser.add_argument("--reason", required=True, help="why it is closed")
    retract_parser = _command(
        commands,
        parent,
        OperationName.RETRACT,
        "stop a PM answer being precedent; it stays delivered and listed",
    )
    retract_parser.add_argument(
        "answer_seq", type=int, help="the answer's seq, from `amoeba decisions`"
    )
    retract_parser.add_argument("--reason", required=True, help="why it is retracted")
    _register_release_commands(commands, parent)
    return parser


def _register_release_commands(commands: Any, parent: argparse.ArgumentParser) -> None:
    """``report-release`` and ``changes`` (slice 227). No flag is ``required=True``:
    an absent flag is left out of the document, so the operation rejects it with the
    same detail on both doors."""
    report_parser = _command(
        commands,
        parent,
        OperationName.REPORT_RELEASE,
        "report what a merge or release changed for the repos that depend on this one",
    )
    report_parser.add_argument("--commit", help="the full hash of the reported commit")
    report_parser.add_argument(
        "--version", help="the release tag, when the commit is a release"
    )
    report_parser.add_argument(
        "--changed", help="what changed, for a user of this repo"
    )
    report_parser.add_argument(
        "--touched",
        action="append",
        help="one thing that changed; repeat for each",
    )
    mode = report_parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--correct",
        action="store_true",
        help="replace the text of a report already made",
    )
    mode.add_argument(
        "--withdraw", action="store_true", help="take a report back entirely"
    )
    changes_parser = _command(
        commands,
        parent,
        OperationName.CHANGES,
        "what this repo's providers reported since a time",
    )
    changes_parser.add_argument(
        "--since",
        metavar="ISO-8601",
        help="start at this time, with a UTC offset",
    )
