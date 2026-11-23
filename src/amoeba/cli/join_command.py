"""``amoeba join`` and ``amoeba leave``: CLI-only commands (slice 260, D4).

They are no ``OperationName`` and have no MCP tool. Neither goes through
``wiring.invoke``: ``join`` reads the client file only for ``--address``, and ``leave``
works with any of the files missing and makes no hub call. Both exit 0 or 3: a
``JoinError`` and every other failure is exit 3, since there is no rejected outcome.
"""

from __future__ import annotations

import argparse
from typing import Any

from amoeba.cli.exit_codes import EXIT_OK
from amoeba.cli.output import print_text_or_json
from amoeba.wiring_door import (
    JOIN_COMMAND,
    LEAVE_COMMAND,
    JoinReport,
    LeaveReport,
    join,
    join_address,
    leave,
)


def register_join(commands: Any, json_parent: argparse.ArgumentParser) -> None:
    parser = commands.add_parser(
        JOIN_COMMAND,
        parents=[json_parent],
        help="join a hub with the line `amoeba hub invite` printed",
    )
    parser.set_defaults(cli_only=JOIN_COMMAND)
    parser.add_argument(
        "line", nargs="?", help="the join line: <address>,<fingerprint>,<token>"
    )
    parser.add_argument(
        "--set-aside-local",
        action="store_true",
        help="set this machine's local store aside (`amoeba leave` puts it back)",
    )
    parser.add_argument(
        "--address",
        metavar="HOST:PORT",
        help="change only the hub's address in the client file; makes no hub call",
    )


def register_leave(commands: Any, json_parent: argparse.ArgumentParser) -> None:
    parser = commands.add_parser(
        LEAVE_COMMAND,
        parents=[json_parent],
        help="leave the hub: put a set-aside local store back and forget the hub",
    )
    parser.set_defaults(cli_only=LEAVE_COMMAND)


def _joined_text(report: JoinReport) -> str:
    lines = [f"joined the hub at {report.address} as {report.machine}"]
    if report.set_aside is not None:
        lines.append(
            f"the local store is set aside at {report.set_aside}; "
            "`amoeba leave` puts it back"
        )
    return "\n".join(lines)


def run_join(parser: argparse.ArgumentParser, arguments: argparse.Namespace) -> int:
    """Run `join`; a usage error exits 2 through ``parser``."""
    line: str | None = arguments.line
    address: str | None = arguments.address
    if (line is None) == (address is None):
        parser.error("join takes a join line, or --address <host:port>, not both")
    if address is not None:
        if arguments.set_aside_local:
            parser.error("--set-aside-local goes with a join line, not --address")
        changed = join_address(address)
        print_text_or_json(
            f"the hub's address is now {changed.address}",
            {"address": changed.address, "machine": changed.machine},
            arguments.json,
        )
        return EXIT_OK
    assert line is not None
    report = join(line, set_aside_local=arguments.set_aside_local)
    print_text_or_json(
        _joined_text(report),
        {
            "machine": report.machine,
            "address": report.address,
            "set_aside": None if report.set_aside is None else str(report.set_aside),
        },
        arguments.json,
    )
    return EXIT_OK


def _left_lines(report: LeaveReport) -> list[str]:
    lines: list[str] = []
    undone = report.put_back
    if undone.displaced is not None:
        lines.append(
            f"a store that was in the way was moved to {undone.displaced}; "
            "nothing of it was deleted"
        )
    if undone.restored is not None:
        lines.append("the local store is back")
    if undone.cleared_mark:
        lines.append("the local store's closed mark was cleared")
    lines.extend(f"removed {path}" for path in report.removed)
    return lines


def run_leave(arguments: argparse.Namespace) -> int:
    """Run `leave`: always exit 0 unless a step fails."""
    report = leave()
    lines = _left_lines(report)
    print_text_or_json(
        "\n".join(lines) if lines else "nothing to do: this machine is not joined",
        {
            "restored": report.put_back.restored is not None,
            "displaced": (
                None
                if report.put_back.displaced is None
                else str(report.put_back.displaced)
            ),
            "cleared_mark": report.put_back.cleared_mark,
            "removed": [str(path) for path in report.removed],
        },
        arguments.json,
    )
    return EXIT_OK
