"""Reduce what the store holds about one finished run to the routing inputs (D1).

:func:`reduce` is pure: no store, no clock. ``gather`` (``evidence.py``) reads the
store into :class:`OutcomeEvidence`, plain data a test can build by hand. Each
rule below is one small helper, so each row of D1 has one place to read.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from amoeba.process import (
    RunCheckpoint,
    RunFailure,
    UnknownKind,
    parse_checkpoint_kind,
    parse_failure_kind,
)
from amoeba.runner.routing.inputs import (
    CLEAR,
    FALSE,
    NEW,
    NODE_BLOCKED,
    NODE_DONE,
    NODE_RUNNABLE,
    NONE,
    OUTCOME_LAUNCH_FAILED,
    RECURRING,
    SEVERITY_LOW_TO_HIGH,
    TRUE,
    UNKNOWN,
    VALUE_SETS,
    VERDICT_WORST_FIRST,
    RoutingInput,
    RoutingInputs,
)
from amoeba.store import (
    BLOCKED_STATUSES,
    FindingChange,
    FindingSeverity,
    NodeStatus,
    ReviewVerdict,
    VerdictStanding,
)


@dataclass(frozen=True)
class ReviewPart:
    """One recorded verdict, as routing reads it.

    ``severity`` is the highest finding severity in the review (``pass`` when it
    has none). ``routed_changes`` tags each ``concern`` or ``fail`` finding as new
    or recurring; ``comparable`` is false when there is no previous round to
    compare with, so recurrence cannot be told.
    """

    verdict: ReviewVerdict
    standing: VerdictStanding
    severity: FindingSeverity
    comparable: bool
    routed_changes: tuple[FindingChange, ...]


@dataclass(frozen=True)
class OutcomeEvidence:
    """Everything the reduction reads, as plain data.

    ``outcome`` is the entry result's ``outcome`` text. ``checkpoint`` and
    ``failure`` are the outcome document's sections, ``None`` when it has none.
    ``attempt_count`` is the node's counted attempts for ``step``, ``None`` when
    the step is not a known one (it cannot be counted). ``review_unreadable`` is
    set when a recorded verdict could not be read back.
    """

    outcome: str | None
    launch_failed: bool
    checkpoint: RunCheckpoint | None
    failure: RunFailure | None
    step: str | None
    node_status: NodeStatus
    attempt_count: int | None
    review_fault: bool
    review_unreadable: bool
    parts: tuple[ReviewPart, ...]


def reduce(evidence: OutcomeEvidence) -> RoutingInputs:
    """The routing inputs for one outcome, and its attempt number."""
    step = _step(evidence)
    values = {
        RoutingInput.OUTCOME: _outcome(evidence),
        RoutingInput.CHECKPOINT_KIND: _checkpoint_kind(evidence.checkpoint),
        RoutingInput.AT_LOOP: _at_loop(evidence.checkpoint),
        RoutingInput.FAILURE_KIND: _failure_kind(evidence.failure),
        RoutingInput.STEP: step,
        RoutingInput.NODE_STATE: _node_state(evidence.node_status),
        **_review_inputs(evidence),
    }
    return RoutingInputs(values, _attempt(evidence, step))


def _outcome(evidence: OutcomeEvidence) -> str:
    if evidence.launch_failed:
        return OUTCOME_LAUNCH_FAILED
    if evidence.outcome is None:
        return UNKNOWN
    return _in_set(RoutingInput.OUTCOME, evidence.outcome)


def _checkpoint_kind(checkpoint: RunCheckpoint | None) -> str:
    if checkpoint is None:
        return NONE
    kind = parse_checkpoint_kind(checkpoint.kind)
    return UNKNOWN if kind is None or isinstance(kind, UnknownKind) else kind.value


def _failure_kind(failure: RunFailure | None) -> str:
    if failure is None:
        return NONE
    kind = parse_failure_kind(failure.kind)
    return UNKNOWN if kind is None or isinstance(kind, UnknownKind) else kind.value


def _at_loop(checkpoint: RunCheckpoint | None) -> str:
    """Only a JSON boolean reduces to true or false; any other type is unknown."""
    if checkpoint is None:
        return NONE
    is_loop = checkpoint.is_loop
    if not isinstance(is_loop, bool):
        return UNKNOWN
    return TRUE if is_loop else FALSE


def _step(evidence: OutcomeEvidence) -> str:
    return _in_set(RoutingInput.STEP, evidence.step)


def _node_state(status: NodeStatus) -> str:
    if status is NodeStatus.RUNNABLE:
        return NODE_RUNNABLE
    if status is NodeStatus.DONE:
        return NODE_DONE
    if status in BLOCKED_STATUSES:
        return NODE_BLOCKED
    # A status the Runner does not write (in_progress) cannot be routed on.
    return UNKNOWN


def _attempt(evidence: OutcomeEvidence, step: str) -> int | None:
    if step == UNKNOWN:
        return None
    if evidence.attempt_count is None:
        raise ValueError(f"step {step} is known but its attempts were not counted")
    return evidence.attempt_count + 1


def _in_set(name: RoutingInput, value: str | None) -> str:
    """``value`` when it is in ``name``'s closed set, else ``unknown``."""
    if value is None or value not in VALUE_SETS[name]:
        return UNKNOWN
    return value


def _review_inputs(evidence: OutcomeEvidence) -> dict[RoutingInput, str]:
    """The four review inputs: none, all unknown, or combined over the parts."""
    names = (
        RoutingInput.VERDICT,
        RoutingInput.STANDING,
        RoutingInput.SEVERITY,
        RoutingInput.RECURRENCE,
    )
    unreadable = (
        evidence.review_fault
        or evidence.review_unreadable
        or any(part.verdict is ReviewVerdict.UNKNOWN for part in evidence.parts)
    )
    if unreadable:
        return dict.fromkeys(names, UNKNOWN)
    if not evidence.parts:
        return dict.fromkeys(names, NONE)
    parts = evidence.parts
    return {
        RoutingInput.VERDICT: _worst_verdict(parts),
        RoutingInput.STANDING: _common_standing(parts),
        RoutingInput.SEVERITY: _highest_severity(parts),
        RoutingInput.RECURRENCE: _recurrence(parts),
    }


def _worst_verdict(parts: Sequence[ReviewPart]) -> str:
    present = {part.verdict for part in parts}
    worst = next(verdict for verdict in VERDICT_WORST_FIRST if verdict in present)
    return worst.value.lower()


def _common_standing(parts: Sequence[ReviewPart]) -> str:
    standings = {part.standing for part in parts}
    if len(standings) != 1:
        return UNKNOWN
    return standings.pop().value


def _highest_severity(parts: Sequence[ReviewPart]) -> str:
    rank: Callable[[FindingSeverity], int] = SEVERITY_LOW_TO_HIGH.index
    return max((part.severity for part in parts), key=rank).value


def _recurrence(parts: Sequence[ReviewPart]) -> str:
    if not all(part.comparable for part in parts):
        return UNKNOWN
    changes = [change for part in parts for change in part.routed_changes]
    if FindingChange.RECURRING in changes:
        return RECURRING
    return NEW if changes else CLEAR
