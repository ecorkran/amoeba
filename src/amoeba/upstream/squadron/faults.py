"""How a detached ``sq`` launch or resume can fail, as plain values."""

from __future__ import annotations

from enum import StrEnum


class LaunchFailure(StrEnum):
    """How a detached launch failed before its run was confirmed."""

    SPAWN_ERROR = "spawn_error"
    EXITED_BEFORE_LINE = "exited_before_line"
    USAGE_ERROR = "usage_error"


class ResumeFailure(StrEnum):
    """How a resume of a paused run failed."""

    REFUSED = "refused"
    EXITED_BEFORE_CLAIM = "exited_before_claim"
    NO_CLAIM_WITHIN_GRACE = "no_claim_within_grace"
    SPAWN_ERROR = "spawn_error"
    RUN_MISSING = "run_missing"
