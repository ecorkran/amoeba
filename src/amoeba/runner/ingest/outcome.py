"""A finished run's outcome, mapped to the block it needs (D6, "The block, by outcome").

Pure: no store, no I/O. The caller blocks the node (if :attr:`OutcomePlan.block`
is set and the node is not already blocked), then records the reviews and resolves
the entry with :attr:`OutcomePlan.entry_outcome`.

Squadron's own text (a checkpoint's kind and step, a failure's kind, step and
message) reaches a block's context or payload only after it is cut to
``STDERR_TAIL_LIMIT_BYTES``, the bound the Runner already puts on text it copies
from outside.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from amoeba.process import RunCheckpoint, RunFailure, RunOutcome
from amoeba.runner.launch import STDERR_TAIL_LIMIT_BYTES
from amoeba.runner.observed import RunEnded, RunVanished
from amoeba.runner.supervise import (
    REASON_AGENT_QUESTION,
    REASON_AUTO_RESUME_EXHAUSTED,
    REASON_FAILED,
    REASON_PAUSED,
    OutcomeClass,
    classify,
    step_of,
)
from amoeba.store import PARAM_RUN_ID, BlockedKind, JournalOutcome

#: Block payload keys, and the reasons a ``HUMAN`` block carries.
PAYLOAD_RUN_ID: Final = PARAM_RUN_ID
PAYLOAD_REASON: Final = "reason"
PAYLOAD_FAILURE: Final = "failure"
PAYLOAD_CHECKPOINT: Final = "checkpoint"
PAYLOAD_STEP: Final = "step"
PAYLOAD_QUESTION: Final = "question"
PAYLOAD_COUNT: Final = "count"
REASON_ORPHANED: Final = "orphaned"
REASON_VANISHED: Final = "vanished"
#: Used by the reissue (D9) when the old attempt's launch log shows the run began.
REASON_STARTED_BEFORE_CRASH: Final = "started_before_crash"

#: What a context says in place of a kind or step Squadron did not report.
UNKNOWN_TEXT: Final = "unknown"


@dataclass(frozen=True)
class BlockPlan:
    """The block a finished run needs. ``payload`` is ``None`` for a checkpoint."""

    kind: BlockedKind
    context: str
    payload: Mapping[str, object] | None


@dataclass(frozen=True)
class OutcomePlan:
    """What to do for a finished run: an optional block and the entry's outcome."""

    block: BlockPlan | None
    entry_outcome: JournalOutcome
    #: The run completed: mark the slice ``done`` in the same transaction (D4).
    complete_node: bool = False


def cut_to_bound(text: str) -> str:
    """``text`` cut to ``STDERR_TAIL_LIMIT_BYTES`` of UTF-8, never mid-character."""
    encoded = text.encode("utf-8")
    if len(encoded) <= STDERR_TAIL_LIMIT_BYTES:
        return text
    return encoded[:STDERR_TAIL_LIMIT_BYTES].decode("utf-8", errors="ignore")


def plan_outcome(finished: RunEnded | RunVanished, run_id: str) -> OutcomePlan:
    """The block and entry outcome for a run that ended, or was found gone.

    Raises:
        ValueError: The document's outcome is not an end state (``timed_out`` is
            a run still going; the others are faults the tick handles).
    """
    if isinstance(finished, RunVanished):
        return _human(
            REASON_VANISHED,
            run_id,
            f"run {run_id} vanished: Squadron has no state for it",
            JournalOutcome.FAILED,
        )
    document = finished.document
    match document.outcome:
        case RunOutcome.COMPLETED:
            return OutcomePlan(None, JournalOutcome.COMPLETED)
        case RunOutcome.PAUSED:
            return OutcomePlan(
                _checkpoint_block(finished, run_id), JournalOutcome.COMPLETED
            )
        case RunOutcome.FAILED:
            return _failed(finished, run_id)
        case RunOutcome.ORPHANED:
            return _human(
                REASON_ORPHANED,
                run_id,
                f"run {run_id} was orphaned",
                JournalOutcome.FAILED,
            )
        case _:
            raise ValueError(
                f"run {run_id} outcome {document.outcome.value} is not an end state"
            )


def _human(
    reason: str,
    run_id: str,
    context: str,
    entry_outcome: JournalOutcome,
    **extra: object,
) -> OutcomePlan:
    payload: dict[str, object] = {
        PAYLOAD_RUN_ID: run_id,
        PAYLOAD_REASON: reason,
        **extra,
    }
    return OutcomePlan(BlockPlan(BlockedKind.HUMAN, context, payload), entry_outcome)


def _checkpoint_block(finished: RunEnded, run_id: str) -> BlockPlan:
    checkpoint = finished.document.checkpoint
    kind = checkpoint.kind if checkpoint else None
    step = checkpoint.step if checkpoint else None
    context = (
        f"paused: {cut_to_bound(kind or UNKNOWN_TEXT)} "
        f"at {cut_to_bound(step or UNKNOWN_TEXT)}, run {run_id}"
    )
    return BlockPlan(BlockedKind.SQ_CHECKPOINT, context, None)


def _failed(finished: RunEnded, run_id: str) -> OutcomePlan:
    failure = finished.document.failure
    kind = failure.kind if failure else None
    return _human(
        REASON_FAILED,
        run_id,
        f"run {run_id} failed: {cut_to_bound(kind or UNKNOWN_TEXT)}",
        JournalOutcome.COMPLETED,
        **{PAYLOAD_FAILURE: _failure_payload(failure)},
    )


def _failure_payload(failure: RunFailure | None) -> dict[str, object] | None:
    """The failure as reported, each text field bounded; ``None`` if none came."""
    if failure is None:
        return None
    fields = {
        "kind": failure.kind,
        "step": failure.step,
        "message": failure.message,
        # Only when Squadron sent it, so a failure without one keeps its old shape.
        **(
            {"agent_text": failure.agent_text} if failure.agent_text is not None else {}
        ),
    }
    return _bounded(fields)


def _bounded(fields: Mapping[str, str | None]) -> dict[str, object]:
    return {
        name: None if value is None else cut_to_bound(value)
        for name, value in fields.items()
    }


def _checkpoint_payload(checkpoint: RunCheckpoint | None) -> dict[str, object] | None:
    """The checkpoint as reported, each text field bounded; ``None`` if none came."""
    if checkpoint is None:
        return None
    return _bounded(
        {
            "kind": checkpoint.kind,
            "step": checkpoint.step,
            "step_type": checkpoint.step_type,
            "reason": checkpoint.reason,
            "review_file": checkpoint.review_file,
        }
    )


def plan_supervised(
    finished: RunEnded | RunVanished, run_id: str, count: int, limit: int
) -> OutcomePlan:
    """The block and entry outcome for a run that ended, by the outcome map (D4).

    ``count`` is :func:`~amoeba.runner.supervise.resume_count` for the run's step and
    ``limit`` the ``auto_resume_limit`` setting; a transient outcome at ``limit``
    blocks instead of being resumed.

    Raises:
        ValueError: The document's outcome is not an end state.
    """
    if isinstance(finished, RunVanished):
        return plan_outcome(finished, run_id)
    resolved = _entry_outcome(finished.document.outcome)
    match classify(finished):
        case OutcomeClass.COMPLETED:
            return OutcomePlan(None, resolved, complete_node=True)
        case OutcomeClass.TRANSIENT:
            if count < limit:
                return OutcomePlan(None, resolved)
            return OutcomePlan(_exhausted_block(finished, run_id, count), resolved)
        case OutcomeClass.QUESTION:
            return OutcomePlan(_question_block(finished, run_id), resolved)
        case OutcomeClass.BLOCKED:
            return _blocked(finished, run_id, resolved)


def _entry_outcome(outcome: RunOutcome) -> JournalOutcome:
    """The entry's outcome for a run that ended: ``failed`` only if it was orphaned."""
    return (
        JournalOutcome.FAILED
        if outcome is RunOutcome.ORPHANED
        else JournalOutcome.COMPLETED
    )


def _question_block(finished: RunEnded, run_id: str) -> BlockPlan:
    checkpoint = finished.document.checkpoint
    step = checkpoint.step if checkpoint else None
    question = checkpoint.question if checkpoint else None
    payload = {
        PAYLOAD_RUN_ID: run_id,
        PAYLOAD_REASON: REASON_AGENT_QUESTION,
        **_bounded({PAYLOAD_STEP: step, PAYLOAD_QUESTION: question}),
    }
    context = f"question at {cut_to_bound(step or UNKNOWN_TEXT)}, run {run_id}"
    # A HUMAN block: the store keeps a payload only on a human block's escalation, and
    # the question must reach the person (and 140) with it.
    return BlockPlan(BlockedKind.HUMAN, context, payload)


def _blocked(finished: RunEnded, run_id: str, resolved: JournalOutcome) -> OutcomePlan:
    document = finished.document
    if document.outcome is RunOutcome.FAILED:
        return _failed(finished, run_id)
    block = _checkpoint_block(finished, run_id)
    payload = {
        PAYLOAD_RUN_ID: run_id,
        PAYLOAD_REASON: REASON_PAUSED,
        PAYLOAD_CHECKPOINT: _checkpoint_payload(document.checkpoint),
    }
    return OutcomePlan(BlockPlan(block.kind, block.context, payload), resolved)


def _exhausted_block(finished: RunEnded, run_id: str, count: int) -> BlockPlan:
    document = finished.document
    step = step_of(document)
    context = (
        f"auto-resume exhausted at {cut_to_bound(step or UNKNOWN_TEXT)} "
        f"after {count} resumes, run {run_id}"
    )
    payload: dict[str, object] = {
        PAYLOAD_RUN_ID: run_id,
        PAYLOAD_REASON: REASON_AUTO_RESUME_EXHAUSTED,
        PAYLOAD_STEP: None if step is None else cut_to_bound(step),
        PAYLOAD_COUNT: count,
    }
    if document.failure is not None:
        payload[PAYLOAD_FAILURE] = _failure_payload(document.failure)
    elif document.checkpoint is not None:
        payload[PAYLOAD_CHECKPOINT] = _checkpoint_payload(document.checkpoint)
    return BlockPlan(BlockedKind.HUMAN, context, payload)
