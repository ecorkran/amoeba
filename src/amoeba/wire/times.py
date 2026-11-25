"""The door version and the shared network times (slice 260, D7).

Every value is defined once here. Tests pin the version together with the times, so
nobody changes a time without changing the version.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: The shape of the door. Raised when the call format or a time changes.
DOOR_VERSION: Final = 3
#: Longest wait to connect, in seconds.
CONNECT_SECONDS: Final = 3.0
#: Longest wait for a reply to one attempt, in seconds.
READ_SECONDS: Final = 10.0
#: A new attempt starts only while less than this has passed since the first.
RETRY_SECONDS: Final = 30.0
#: Wait between attempts, in seconds.
RETRY_PAUSE_SECONDS: Final = 0.5
#: The longest a call can take: the last attempt starts just before the retry time.
CALL_BOUND_SECONDS: Final = RETRY_SECONDS + CONNECT_SECONDS + READ_SECONDS
#: How long the hub keeps a writing call's result.
CALL_RESULT_LIFETIME_SECONDS: Final = 600.0
#: The longest any MCP call may take (263 D9). It must exceed ``answer_bound_seconds``
#: for a sane config (150.5 s for the config contract's example) and the hub part of
#: ``answer`` on the door, so it cannot sit under Codex's default tool timeout of 60 s;
#: the install doc tells Codex users to raise ``tool_timeout_sec`` to at least this
#: plus 5. Claude Code's default is about 28 hours. A change is a door version change:
#: the hub checks ``answer`` against it.
MCP_CALL_DEADLINE_SECONDS: Final = 300.0


@dataclass(frozen=True)
class DoorTimes:
    """The times one call uses. Defaults are the constants; tests pass shorter ones."""

    connect_seconds: float = CONNECT_SECONDS
    read_seconds: float = READ_SECONDS
    retry_seconds: float = RETRY_SECONDS
    retry_pause_seconds: float = RETRY_PAUSE_SECONDS


#: A session's tick is one attempt: the next tick is the retry (263 D4). A retry time
#: of 0 gives it no retry of its own; ``session_tick`` also keeps no result, so a
#: repeat of it is always safe.
TICK_TIMES: Final = DoorTimes(retry_seconds=0.0)
#: The longest a tick's call takes: one connect and one read.
TICK_BOUND_SECONDS: Final = CONNECT_SECONDS + READ_SECONDS
