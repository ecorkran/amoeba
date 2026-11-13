"""The closed vocabularies both doors share (slice 226, D3, D11).

``OperationName`` is every operation's name once: the CLI registers its
subcommands from it and the MCP tool table names its tools from it. ``Door`` is the
way a call reached Amoeba; it is defined in ``store.vocabulary`` (the store records
it, and the store imports nothing from ``operations``) and re-exported here.
"""

from __future__ import annotations

from enum import StrEnum

from amoeba.store.vocabulary import Door

__all__ = ["Door", "OperationName"]


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
