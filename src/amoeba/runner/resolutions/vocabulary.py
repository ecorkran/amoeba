"""The resolution vocabulary, defined once (slice 127, D2 and D3).

Every value a PM's resolution can name, every situation it is judged in, every
reason it can be rejected for, and the payload keys a rejection or a stop writes.
Nothing else in the Runner spells these out: tests and consumers import them.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Final


class ResolutionDecision(StrEnum):
    """What a PM can decide when resolving a blocked pipeline step."""

    RETRY = "retry"
    ACCEPT = "accept"
    HANDLED = "handled"
    RERUN = "rerun"
    STOP = "stop"


class Situation(StrEnum):
    """Where a blocked step stands, which sets the decisions it can take."""

    NO_DECISION = "no_decision"
    PAUSED_RUN = "paused_run"
    COMPLETED_OUTCOME = "completed_outcome"
    ENDED_RUN = "ended_run"
    BEFORE_RUN = "before_run"
    UNRESOLVABLE = "unresolvable"


class ResolutionRejection(StrEnum):
    """Why the Runner refused a resolution. Stored as ``runner_code``."""

    UNKNOWN_DECISION = "unknown_decision"
    DECISION_REQUIRED = "decision_required"
    DECISION_NOT_APPLICABLE = "decision_not_applicable"
    NOT_AT_LOOP = "not_at_loop"
    USAGE_LIMIT_PAUSE = "usage_limit_pause"
    CHECKPOINT_UNKNOWN = "checkpoint_unknown"
    INTERACTIVE_CHECKPOINT = "interactive_checkpoint"
    INSTRUCTIONS_NOT_APPLICABLE = "instructions_not_applicable"
    UNRESOLVABLE = "unresolvable"


class Continuation(StrEnum):
    """What a continuation journal entry does with an earlier run (D4)."""

    RETRY = "retry"
    ACCEPT = "accept"
    OBSERVE = "observe"


_DECISIONS = ResolutionDecision

#: The decisions each situation allows (D2). A situation absent of decisions
#: rejects every one that names one.
ALLOWED: Final[Mapping[Situation, frozenset[ResolutionDecision]]] = {
    Situation.NO_DECISION: frozenset(),
    Situation.PAUSED_RUN: frozenset(
        {_DECISIONS.RETRY, _DECISIONS.ACCEPT, _DECISIONS.HANDLED, _DECISIONS.STOP}
    ),
    Situation.COMPLETED_OUTCOME: frozenset(
        {_DECISIONS.ACCEPT, _DECISIONS.RERUN, _DECISIONS.STOP}
    ),
    Situation.ENDED_RUN: frozenset({_DECISIONS.RERUN, _DECISIONS.STOP}),
    Situation.BEFORE_RUN: frozenset({_DECISIONS.RERUN, _DECISIONS.STOP}),
    Situation.UNRESOLVABLE: frozenset(),
}

#: The ``reason`` a rejection's or a stop's block payload carries (D3).
REASON_RESOLUTION_REJECTED: Final = "resolution_rejected"
REASON_STOPPED: Final = "stopped"
#: The ``reason`` a failed resume's block payload carries (D6).
REASON_RESUME_FAILED: Final = "resume_failed"

#: Payload keys of a rejection block (D3) and of a stop block.
PAYLOAD_CODE: Final = "code"
PAYLOAD_DETAIL: Final = "detail"
PAYLOAD_REJECTED_BLOCKED_STATE_ID: Final = "rejected_blocked_state_id"
PAYLOAD_ALLOWED: Final = "allowed"
PAYLOAD_STOPPED_BLOCKED_STATE_ID: Final = "stopped_blocked_state_id"

#: A resume skipped because its run was no longer at the pause the PM resolved
#: (D4). Journaled as a parameter of the observation entry.
PARAM_RESUME_SKIPPED: Final = "resume_skipped"
RESUME_SKIPPED_RUN_NOT_AT_PAUSE: Final = "run_not_at_pause"
