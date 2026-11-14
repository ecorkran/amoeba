"""The closed vocabularies both doors share (slice 226, D3, D11).

``OperationName`` is every operation's name once: the CLI registers its
subcommands from it and the MCP tool table names its tools from it. ``Door`` is the
way a call reached Amoeba; it is defined in ``store.vocabulary`` (the store records
it, and the store imports nothing from ``operations``) and re-exported here.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from amoeba.store.vocabulary import Door

#: The command a person types; the doors build command text from it and ``cli_name``.
PROGRAM_NAME: Final = "amoeba"

__all__ = ["PROGRAM_NAME", "Door", "OperationName"]


class OperationName(StrEnum):
    """An operation's name: the CLI subcommand and the MCP tool name."""

    ADD = "add"
    RM = "rm"
    LIST = "list"
    HANDLE_PAUSE = "handle_pause"
    ANSWER = "answer"
    STATUS = "status"
    DECISIONS = "decisions"
    MARK_READ = "mark_read"
    DISMISS = "dismiss"
    RETRACT = "retract"

    @property
    def cli_name(self) -> str:
        """The command-line form: the value with ``_`` as ``-`` (``handle-pause``)."""
        return self.value.replace("_", "-")
