"""The resolution vocabulary, defined once (slice 127, D2 and D3; slice 132, D6).

Every value a PM's resolution can name, every situation it is judged in, every
reason it can be rejected for, and the payload keys a rejection or a stop writes.
Nothing else in the Runner spells these out: tests and consumers import them.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Final


class ResolutionDecision(StrEnum):
    """What a PM can decide when resolving a blocked slice (slice 132, D6)."""

    RESUME = "resume"
    STOP = "stop"


class Situation(StrEnum):
    """Where a blocked slice stands, which is all a resolution is judged on."""

    #: The latest run is one Squadron still has: paused, failed or orphaned.
    RUN_TO_RESUME = "run_to_resume"
    #: No run to resume: a launch failed, the run vanished, or the block came
    #: before any run.
    NO_RUN = "no_run"
    UNRESOLVABLE = "unresolvable"


class ResolutionRejection(StrEnum):
    """Why the Runner refused a resolution. Stored as ``runner_code``."""

    UNKNOWN_DECISION = "unknown_decision"
    DECISION_REQUIRED = "decision_required"
    INSTRUCTIONS_NOT_APPLICABLE = "instructions_not_applicable"
    UNRESOLVABLE = "unresolvable"


class Continuation(StrEnum):
    """What marks a journal entry as a resume of an earlier run (D5)."""

    RESUME = "resume"


_DECISIONS = ResolutionDecision

#: The decisions each situation allows. A situation absent of decisions rejects
#: every resolution that names one.
ALLOWED: Final[Mapping[Situation, frozenset[ResolutionDecision]]] = {
    Situation.RUN_TO_RESUME: frozenset({_DECISIONS.RESUME, _DECISIONS.STOP}),
    Situation.NO_RUN: frozenset({_DECISIONS.RESUME, _DECISIONS.STOP}),
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

#: Why a resume was issued, journaled on the resume entry (slice 132, D5 and D6).
PARAM_RESUME_CAUSE: Final = "resume_cause"


class ResumeCause(StrEnum):
    """What caused a resume: the supervisor retrying, or a PM's resolution."""

    TRANSIENT = "transient"
    RESOLUTION = "resolution"


#: A resume skipped because its run was no longer in the state it was resumed from
#: (D4). Journaled as a parameter of the observation entry.
PARAM_RESUME_SKIPPED: Final = "resume_skipped"
RESUME_SKIPPED_RUN_NOT_AT_PAUSE: Final = "run_not_at_pause"
