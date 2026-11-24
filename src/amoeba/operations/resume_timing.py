"""The waits a resume is made of, defined once (slice 262, D6).

A leaf module: ``operations.steps`` works out the resume claim's limit from these
without importing anything that runs ``sq``, and ``resume`` works out its own bound
from the same values.
"""

from __future__ import annotations

from typing import Final

from amoeba.config.user_config import UserConfig

#: One ``sq runs wait --timeout 0`` call reads a run file; a call this long is stuck.
RUN_POLL_TIMEOUT_SECONDS: Final = 30.0
#: How long a stopped child gets to exit after SIGTERM before it is killed.
TERMINATE_GRACE_SECONDS: Final = 5.0
#: How often the run is polled while the resume child is starting (223 D8).
RESUME_POLL_INTERVAL_SECONDS: Final = 0.5


def resume_work_seconds(config: UserConfig) -> float:
    """What a resume can take apart from its writes to the store.

    The wait loop and its last poll, the SIGTERM grace and then the SIGKILL grace in
    ``terminate_group``, and the poll after the kill with the first poll before the
    spawn.
    """
    return (
        config.resume_wait_seconds
        + RESUME_POLL_INTERVAL_SECONDS
        + 2 * RUN_POLL_TIMEOUT_SECONDS
        + 2 * TERMINATE_GRACE_SECONDS
    )
