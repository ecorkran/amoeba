"""Judge a resolution against its situation (slice 127, D2 and D3).

Pure. Every problem in the resolution's inputs is a rejection, an answer the
caller records, never an exception: expected data must not stop a tick. The first
failing check, in D2's order, is the rejection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from pydantic import ValidationError

from amoeba.process import (
    CheckpointKind,
    RunCheckpoint,
    RunOutcomeDocument,
    parse_checkpoint_kind,
)
from amoeba.runner.ingest.outcome import PAYLOAD_REASON
from amoeba.runner.ingest.record import RESULT_OUTCOME_DOCUMENT
from amoeba.runner.resolutions.vocabulary import (
    ALLOWED,
    PAYLOAD_ALLOWED,
    PAYLOAD_CODE,
    PAYLOAD_DETAIL,
    PAYLOAD_REJECTED_BLOCKED_STATE_ID,
    PAYLOAD_STOPPED_BLOCKED_STATE_ID,
    REASON_RESOLUTION_REJECTED,
    REASON_STOPPED,
    ResolutionDecision,
    ResolutionRejection,
    Situation,
)
from amoeba.store import (
    BlockedState,
    BlockEffect,
    JournalEntry,
    NodeStatus,
    ResolutionOutcome,
    StatusEffect,
)

#: The decisions that carry the PM's instructions to Squadron.
_TAKES_INSTRUCTIONS: Final = frozenset(
    {ResolutionDecision.RETRY, ResolutionDecision.ACCEPT}
)


@dataclass(frozen=True)
class Acknowledgment:
    """The Runner's answer to one resolution, and the effect that goes with it."""

    outcome: ResolutionOutcome
    code: str | None
    reason: str | None
    effect: StatusEffect | BlockEffect | None


def checkpoint_of(entry: JournalEntry | None) -> RunCheckpoint | None:
    """The checkpoint in the entry's recorded outcome document, or ``None``.

    A missing entry, document or checkpoint, and a document that does not parse,
    all give ``None``: unknown is a value, and it never raises.
    """
    document = (
        None
        if entry is None or entry.result is None
        else entry.result.get(RESULT_OUTCOME_DOCUMENT)
    )
    if not isinstance(document, dict):
        return None
    try:
        return RunOutcomeDocument.model_validate(document).checkpoint
    except ValidationError:
        # A stored document that no longer fits the model is unknown, not a fault.
        return None


def judge_resolution(
    blocked: BlockedState, situation: Situation, checkpoint: RunCheckpoint | None
) -> Acknowledgment:
    """Answer one resolved blocked state.

    Raises:
        ValueError: If ``blocked`` has no resolution, a programming error.
    """
    if blocked.resolution is None:
        raise ValueError(f"blocked state {blocked.id} is not resolved")
    decision = blocked.resolution.decision
    instructions = blocked.resolution.instructions
    rejection = _first_rejection(decision, instructions, situation, checkpoint)
    if rejection is not None:
        return _rejected(blocked, situation, *rejection)
    known = _decision_of(decision)
    if known is ResolutionDecision.STOP:
        return _stopped(blocked, blocked.resolution.resolved_by)
    if known is ResolutionDecision.ACCEPT and situation is Situation.COMPLETED_OUTCOME:
        return _applied(StatusEffect(NodeStatus.DONE))
    return _applied(None)


def _first_rejection(
    decision: str | None,
    instructions: str | None,
    situation: Situation,
    checkpoint: RunCheckpoint | None,
) -> tuple[ResolutionRejection, str] | None:
    """Checks 0 to 7 of D2, in order: the first failure, with its detail."""
    if situation is Situation.UNRESOLVABLE:
        return (
            ResolutionRejection.UNRESOLVABLE,
            "the step's latest entry is unresolved or its outcome is not yet routed",
        )
    known = _decision_of(decision)
    if decision is not None and known is None:
        return ResolutionRejection.UNKNOWN_DECISION, f"unknown decision {decision!r}"
    if known is None:
        if situation is Situation.NO_DECISION:
            return None
        return (
            ResolutionRejection.DECISION_REQUIRED,
            "name one of the allowed decisions",
        )
    if known not in ALLOWED[situation]:
        return (
            ResolutionRejection.DECISION_NOT_APPLICABLE,
            f"{known.value} is not allowed for a {situation.value}",
        )
    if situation is Situation.PAUSED_RUN:
        paused = _paused_run_rejection(known, checkpoint)
        if paused is not None:
            return paused
    if instructions is not None and known not in _TAKES_INSTRUCTIONS:
        return (
            ResolutionRejection.INSTRUCTIONS_NOT_APPLICABLE,
            f"{known.value} takes no instructions",
        )
    return None


def _paused_run_rejection(
    decision: ResolutionDecision, checkpoint: RunCheckpoint | None
) -> tuple[ResolutionRejection, str] | None:
    """Checks 4 to 6: what retry and accept need of the pause they continue."""
    if decision not in _TAKES_INSTRUCTIONS:
        return None
    kind = None if checkpoint is None else checkpoint.kind
    if decision == ResolutionDecision.ACCEPT:
        if checkpoint is None or checkpoint.is_loop is not True:
            return ResolutionRejection.NOT_AT_LOOP, "the pause is not at a loop"
        if parse_checkpoint_kind(kind) is CheckpointKind.USAGE_LIMIT:
            return (
                ResolutionRejection.USAGE_LIMIT_PAUSE,
                "the paused round never ran; retry after the limit resets",
            )
    if checkpoint is None or kind is None or checkpoint.paused_at is None:
        return (
            ResolutionRejection.CHECKPOINT_UNKNOWN,
            "the run's checkpoint kind or pause time is not known",
        )
    if (
        decision == ResolutionDecision.RETRY
        and parse_checkpoint_kind(kind) is CheckpointKind.INTERACTIVE_CHECKPOINT
    ):
        return (
            ResolutionRejection.INTERACTIVE_CHECKPOINT,
            "resume it interactively, then submit handled",
        )
    return None


def _decision_of(decision: str | None) -> ResolutionDecision | None:
    try:
        return None if decision is None else ResolutionDecision(decision)
    except ValueError:
        # Outside the vocabulary: the caller turns this into unknown_decision.
        return None


def _applied(effect: StatusEffect | BlockEffect | None) -> Acknowledgment:
    return Acknowledgment(ResolutionOutcome.APPLIED, None, None, effect)


def _rejected(
    blocked: BlockedState,
    situation: Situation,
    code: ResolutionRejection,
    detail: str,
) -> Acknowledgment:
    """A rejection blocks the node again so the PM is told (D3)."""
    block = BlockEffect(
        context=f"resolution rejected: {code.value}",
        payload={
            PAYLOAD_REASON: REASON_RESOLUTION_REJECTED,
            PAYLOAD_CODE: code.value,
            PAYLOAD_DETAIL: detail,
            PAYLOAD_REJECTED_BLOCKED_STATE_ID: blocked.id,
            PAYLOAD_ALLOWED: sorted(d.value for d in ALLOWED[situation]),
        },
    )
    return Acknowledgment(ResolutionOutcome.REJECTED, code.value, detail, block)


def _stopped(blocked: BlockedState, resolved_by: str) -> Acknowledgment:
    """Stop parks the node as a block; the PM resolves it to start again."""
    block = BlockEffect(
        context=f"stopped by {resolved_by}",
        payload={
            PAYLOAD_REASON: REASON_STOPPED,
            PAYLOAD_STOPPED_BLOCKED_STATE_ID: blocked.id,
        },
    )
    return _applied(block)
