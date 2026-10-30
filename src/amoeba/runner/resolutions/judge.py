"""Judge a resolution against its situation (slice 127, D2 and D3; slice 132, D6).

Pure. Every problem in the resolution's inputs is a rejection, an answer the
caller records, never an exception: expected data must not stop a tick. The first
failing check is the rejection.
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.runner.ingest.outcome import PAYLOAD_REASON
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
    ResolutionOutcome,
    StatusEffect,
)


@dataclass(frozen=True)
class Acknowledgment:
    """The Runner's answer to one resolution, and the effect that goes with it."""

    outcome: ResolutionOutcome
    code: str | None
    reason: str | None
    effect: StatusEffect | BlockEffect | None


def judge_resolution(blocked: BlockedState, situation: Situation) -> Acknowledgment:
    """Answer one resolved blocked state.

    Raises:
        ValueError: If ``blocked`` has no resolution, a programming error.
    """
    if blocked.resolution is None:
        raise ValueError(f"blocked state {blocked.id} is not resolved")
    decision = blocked.resolution.decision
    rejection = _first_rejection(
        decision, blocked.resolution.has_instructions, situation
    )
    if rejection is not None:
        return _rejected(blocked, situation, *rejection)
    if _decision_of(decision) is ResolutionDecision.STOP:
        return _stopped(blocked, blocked.resolution.resolved_by)
    return _applied(None)


def _first_rejection(
    decision: str | None, has_instructions: bool, situation: Situation
) -> tuple[ResolutionRejection, str] | None:
    """The first failing check, with its detail, or ``None``."""
    if situation is Situation.UNRESOLVABLE:
        return (
            ResolutionRejection.UNRESOLVABLE,
            "the slice's latest entry is unresolved",
        )
    known = _decision_of(decision)
    if decision is not None and known is None:
        return ResolutionRejection.UNKNOWN_DECISION, f"unknown decision {decision!r}"
    if known is None:
        return (
            ResolutionRejection.DECISION_REQUIRED,
            "name one of the allowed decisions",
        )
    if has_instructions and not _takes_instructions(known, situation):
        return (
            ResolutionRejection.INSTRUCTIONS_NOT_APPLICABLE,
            _no_instructions_detail(known),
        )
    return None


def _takes_instructions(decision: ResolutionDecision, situation: Situation) -> bool:
    """Only a resume of a run carries the PM's text: a fresh launch cannot."""
    return (
        decision is ResolutionDecision.RESUME and situation is Situation.RUN_TO_RESUME
    )


def _no_instructions_detail(decision: ResolutionDecision) -> str:
    if decision is ResolutionDecision.RESUME:
        return "there is no run to resume, and a fresh launch carries no instructions"
    return f"{decision.value} takes no instructions"


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
