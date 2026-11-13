"""The closed vocabularies both doors share (slice 226, D3, D11).

``OperationName`` is every operation's name once: the CLI registers its
subcommands from it and the MCP tool table names its tools from it. ``Door`` is the
way an answer reached Amoeba, recorded beside each PM answer.
"""

from __future__ import annotations

from enum import StrEnum


class OperationName(StrEnum):
    """An operation's name: the CLI subcommand and the MCP tool name."""

    SET_UP = "set_up"
    HANDLE_PAUSE = "handle_pause"
    ANSWER = "answer"
    STATUS = "status"
    DECISIONS = "decisions"
    MARK_READ = "mark_read"
    DISMISS = "dismiss"
    RETRACT = "retract"


class Door(StrEnum):
    """Which interface carried a call: the command line or the MCP server."""

    CLI = "cli"
    MCP = "mcp"
