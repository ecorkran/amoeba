"""Reduce what the store holds about one finished run to the routing inputs (D1).

:func:`reduce` is pure: no store, no clock. ``gather`` (``evidence.py``) reads the
store into :class:`OutcomeEvidence`, plain data a test can build by hand. Each
rule below is one small helper, so each row of D1 has one place to read.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from amoeba.process import (
    RunCheckpoint,
    RunFailure,
    RunOutcome,
    UnknownKind,
    parse_checkpoint_kind,
    parse_failure_kind,
)
from amoeba.runner.gates.cf_status import EXIT_GATE
from amoeba.runner.gates.outcome import gate_state_at_exit
from amoeba.runner.lifecycle.steps import LifecycleStep
from amoeba.runner.resolutions.vocabulary import Continuation
from amoeba.runner.routing.inputs import (
    CLEAR,
    FALSE,
    NEW,
    NODE_BLOCKED,
    NODE_DONE,
    NODE_RUNNABLE,
    NONE,
    OUTCOME_LAUNCH_FAILED,
    OUTCOME_RESUME_FAILED,
    RECURRING,
    SEVERITY_LOW_TO_HIGH,
    STANDING_WORST_FIRST,
    TRUE,
    UNKNOWN,
    VALUE_SETS,
    VERDICT_WORST_FIRST,
    RoutingInput,
    RoutingInputs,
)
from amoeba.store import (
    BLOCKED_STATUSES,
    CheckStanding,
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

    ``outcome`` is the entry result's ``outcome`` text. ``resume_failed`` is set when
    the result carries a ``resume_failure`` and wins over ``outcome``, as
    ``launch_failed`` does. ``continuation`` is the entry's continuation (``retry``,
    ``accept`` or ``observe``), ``None`` for an ordinary run; ``verdict_ids`` are the
    entry's recorded reviews and ``continued_verdict_ids`` those of the entry it
    continues, ``None`` when that entry could not be read. ``checkpoint`` and
    ``failure`` are the outcome document's sections, ``None`` when it has none.
    ``attempt_count`` is the node's counted attempts for ``step``, ``None`` when
    the step is not a known one (it cannot be counted). ``review_unreadable`` is
    set when a recorded verdict could not be read back.
    """

    outcome: str | None
    launch_failed: bool
    resume_failed: bool
    continuation: str | None
    verdict_ids: tuple[str, ...]
    continued_verdict_ids: tuple[str, ...] | None
    checkpoint: RunCheckpoint | None
    failure: RunFailure | None
    step: str | None
    node_status: NodeStatus
    attempt_count: int | None
    review_fault: bool
    review_unreadable: bool
    parts: tuple[ReviewPart, ...]
    #: The stored ``outcome_observation.gate`` (slice 128), ``None`` when the entry
    #: carries no observation: it was ingested before the gates existed.
    gate_record: Mapping[str, object] | None
    #: The standing of each check the entry names, ``None`` for an id the store does
    #: not hold; the whole field is ``None`` when the entry names no checks.
    check_standings: tuple[CheckStanding | None, ...] | None


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
        RoutingInput.REVIEW_ACCEPTED: _review_accepted(evidence),
        RoutingInput.GATE_STATE: _gate_state(evidence, step),
        RoutingInput.CHECK_STANDING: _check_standing(evidence),
        **_review_inputs(evidence),
    }
    return RoutingInputs(values, _attempt(evidence, step))


def _outcome(evidence: OutcomeEvidence) -> str:
    if evidence.launch_failed:
        return OUTCOME_LAUNCH_FAILED
    if evidence.resume_failed:
        return OUTCOME_RESUME_FAILED
    if evidence.outcome is None:
        return UNKNOWN
    return _in_set(RoutingInput.OUTCOME, evidence.outcome)


def _completed(evidence: OutcomeEvidence) -> bool:
    return _outcome(evidence) == RunOutcome.COMPLETED.value


def _gate_state(evidence: OutcomeEvidence, step: str) -> str:
    """CF's gate against the step's exit gate; ``none`` unless the run completed."""
    if not _completed(evidence):
        return NONE
    if step == UNKNOWN or LifecycleStep(step) not in EXIT_GATE:
        return UNKNOWN
    return gate_state_at_exit(LifecycleStep(step), evidence.gate_record)


def _check_standing(evidence: OutcomeEvidence) -> str:
    """The worst check standing; ``unknown`` if a check is missing or unreported."""
    if not _completed(evidence):
        return NONE
    standings = evidence.check_standings
    if not standings or any(standing is None for standing in standings):
        return UNKNOWN
    present = {standing for standing in standings if standing is not None}
    return next(s for s in STANDING_WORST_FIRST if s in present).value


def _review_accepted(evidence: OutcomeEvidence) -> str:
    """``true`` when an accepted loop ended on the review the PM accepted (D8)."""
    if evidence.continuation != Continuation.ACCEPT.value:
        return NONE
    if evidence.continued_verdict_ids is None:
        return UNKNOWN
    same = evidence.verdict_ids == evidence.continued_verdict_ids
    return TRUE if same else FALSE


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
