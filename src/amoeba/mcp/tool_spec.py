"""What a tool row is (slice 226, D2, D12): shared by the tool table and its parts.

Split from ``tools`` so a group of rows (``message_tools``) can be built without a
circular import.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from pydantic import BaseModel

from amoeba.operations.names import OperationName

#: What an agent does when ``status`` or ``decisions`` timed out (D12): the CLI has no
#: deadline, so it is the way through; never the tool that just timed out.
READ_ADVICE: Final = (
    "it was abandoned and may still finish; run the `amoeba` command of the same "
    "name in a shell, which has no deadline, instead of calling this tool again"
)
#: What an agent does when a write tool timed out (D12): the work may have happened.
WRITE_ADVICE: Final = (
    "it may still complete; check `status` or `decisions` before repeating it"
)


class RunMode(StrEnum):
    """How a tool runs: in a worker thread of the server, or as a detached child."""

    IN_PROCESS = "in_process"
    DETACHED = "detached"


@dataclass(frozen=True)
class ToolSpec:
    """One tool: its operation, input, run mode, description and timeout advice."""

    name: OperationName
    request_model: type[BaseModel]
    takes_directory: bool
    mode: RunMode
    description: str
    #: What the agent does when the call times out; ``None`` for a detached tool,
    #: which returns a receipt at once and has no deadline to hit.
    timeout_advice: str | None
