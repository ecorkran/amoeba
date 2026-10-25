"""The routing vocabulary: the named inputs, each one's closed value set (D1).

Code defines the inputs and their values; the routing table only names them. Two
values are shared by many inputs: ``none`` means the input does not apply to this
outcome, and ``unknown`` means it should apply and could not be read. Neither is
ever a default, and ``unknown`` satisfies a rule only when the rule names it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from amoeba.process import CheckpointKind, FailureKind, RunOutcome
from amoeba.runner.ingest.record import OUTCOME_VANISHED
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.store import FindingSeverity, ReviewVerdict, VerdictStanding

#: The input does not apply to this outcome (a completed run has no checkpoint).
NONE: Final = "none"
#: The input should apply and could not be read.
UNKNOWN: Final = "unknown"

#: The outcome of a launch that never produced a run (122's launch failure).
OUTCOME_LAUNCH_FAILED: Final = "launch_failed"

#: JSON booleans as routing values, for ``at_loop``.
TRUE: Final = "true"
FALSE: Final = "false"


class RoutingInput(StrEnum):
    """The closed set of inputs a routing rule may name."""

    OUTCOME = "outcome"
    CHECKPOINT_KIND = "checkpoint_kind"
    AT_LOOP = "at_loop"
    FAILURE_KIND = "failure_kind"
    VERDICT = "verdict"
    STANDING = "standing"
    SEVERITY = "severity"
    RECURRENCE = "recurrence"
    STEP = "step"
    NODE_STATE = "node_state"


#: ``recurrence`` values (a finding-level tag folded over one outcome, D1).
RECURRING: Final = "recurring"
NEW: Final = "new"
CLEAR: Final = "clear"

#: ``node_state`` values.
NODE_RUNNABLE: Final = "runnable"
NODE_BLOCKED: Final = "blocked"
NODE_DONE: Final = "done"

#: Only findings at these severities move routing; a recurring note does not.
ROUTED_SEVERITIES: Final = frozenset({FindingSeverity.CONCERN, FindingSeverity.FAIL})

#: Split-review verdicts combine to the worst part: first in this order wins.
VERDICT_WORST_FIRST: Final = (
    ReviewVerdict.FAIL,
    ReviewVerdict.CONCERNS,
    ReviewVerdict.PASS,
)

#: Severities from lowest to highest, for taking the highest across parts.
SEVERITY_LOW_TO_HIGH: Final = (
    FindingSeverity.PASS,
    FindingSeverity.NOTE,
    FindingSeverity.CONCERN,
    FindingSeverity.FAIL,
)


def _values(*members: str) -> frozenset[str]:
    return frozenset(members)


_OUTCOMES: Final = (
    RunOutcome.COMPLETED.value,
    RunOutcome.PAUSED.value,
    RunOutcome.FAILED.value,
    RunOutcome.ORPHANED.value,
    OUTCOME_VANISHED,
    OUTCOME_LAUNCH_FAILED,
)

#: Each input's closed value set. Every set holds ``unknown``.
VALUE_SETS: Final[Mapping[RoutingInput, frozenset[str]]] = MappingProxyType(
    {
        RoutingInput.OUTCOME: _values(*_OUTCOMES, UNKNOWN),
        RoutingInput.CHECKPOINT_KIND: _values(
            *(kind.value for kind in CheckpointKind), NONE, UNKNOWN
        ),
        RoutingInput.AT_LOOP: _values(TRUE, FALSE, NONE, UNKNOWN),
        RoutingInput.FAILURE_KIND: _values(
            *(kind.value for kind in FailureKind), NONE, UNKNOWN
        ),
        RoutingInput.VERDICT: _values(
            *(v.value.lower() for v in VERDICT_WORST_FIRST), NONE, UNKNOWN
        ),
        RoutingInput.STANDING: _values(
            *(standing.value for standing in VerdictStanding), NONE, UNKNOWN
        ),
        RoutingInput.SEVERITY: _values(
            *(severity.value for severity in FindingSeverity), NONE, UNKNOWN
        ),
        RoutingInput.RECURRENCE: _values(RECURRING, NEW, CLEAR, NONE, UNKNOWN),
        RoutingInput.STEP: _values(*(step.value for step in LifecycleStep), UNKNOWN),
        RoutingInput.NODE_STATE: _values(
            NODE_RUNNABLE, NODE_BLOCKED, NODE_DONE, UNKNOWN
        ),
    }
)


@dataclass(frozen=True)
class RoutingInputs:
    """Every input's value for one outcome, plus the run's attempt number.

    ``attempt`` is ``attempt_count + 1`` for the outcome's step, or ``None`` when
    the step is ``unknown`` and cannot be counted (D1, "Attempts"). It is recorded
    with the decision but is not a matchable input.
    """

    values: Mapping[RoutingInput, str]
    attempt: int | None

    def __post_init__(self) -> None:
        missing = [name.value for name in RoutingInput if name not in self.values]
        if missing:
            raise ValueError(f"routing inputs missing: {', '.join(missing)}")
        for name, value in self.values.items():
            if value not in VALUE_SETS[name]:
                raise ValueError(f"routing input {name.value} has no value {value!r}")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
