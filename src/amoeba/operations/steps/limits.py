"""The limits the steps judge claims by, each defined once (slice 262, D5, D6, D10).

Every place that asks whether a claim is dead imports its limit from here, so the
local way and the hub way cannot differ.
"""

from __future__ import annotations

from typing import Final

from amoeba.config.user_config import UserConfig
from amoeba.operations.resume_timing import resume_work_seconds
from amoeba.store.wakes import WakeLimits
from amoeba.wire.times import CALL_BOUND_SECONDS

#: A claim's reply can arrive one call bound late and its closing call can take one
#: more: the claimant's own limits sit inside those two bounds.
CLAIM_CALL_BOUNDS: Final = 2

#: Automatic starts of one question, and of one answer's resume, that ``claim_work``
#: hands out before it gives up on the row (D10).
MAX_AUTOMATIC_STARTS: Final = 3

#: Items one ``claim_work`` returns; the rest wait for the next call (D10).
MAX_WORK_PER_CLAIM: Final = 5


def pause_claim_seconds(config: UserConfig) -> float:
    """How old a pause claim is, from ``updated_at``, when it counts as dead (D5).

    The answering run's own wait, plus the two call bounds around it. Not the least
    time between two starts of one row: that stays ``answering_wait_seconds``.
    """
    return config.answering_wait_seconds + CLAIM_CALL_BOUNDS * CALL_BOUND_SECONDS


def resume_claim_seconds(config: UserConfig) -> float:
    """How old a resume claim is when another attempt may take it (D6).

    The resume's own bound with the two call bounds in place of its one store wait.
    """
    return resume_work_seconds(config) + CLAIM_CALL_BOUNDS * CALL_BOUND_SECONDS


def wake_limits(config: UserConfig) -> WakeLimits:
    """The limits a wake claim and a due-check apply, from the config."""
    return WakeLimits(
        timeout_seconds=config.wake_timeout_seconds,
        max_per_day=config.max_wakes_per_day,
        session_stale_seconds=config.session_stale_seconds,
    )
