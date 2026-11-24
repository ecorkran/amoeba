"""The door version and the shared network times (slice 260, D7).

Every value is defined once here. Tests pin the version together with the times, so
nobody changes a time without changing the version.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: The shape of the door. Raised when the call format or a time changes.
DOOR_VERSION: Final = 2
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


@dataclass(frozen=True)
class DoorTimes:
    """The times one call uses. Defaults are the constants; tests pass shorter ones."""

    connect_seconds: float = CONNECT_SECONDS
    read_seconds: float = READ_SECONDS
    retry_seconds: float = RETRY_SECONDS
    retry_pause_seconds: float = RETRY_PAUSE_SECONDS
