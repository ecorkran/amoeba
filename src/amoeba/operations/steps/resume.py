"""The resume steps' hub side (slice 262, D4, D6).

``claim_resume`` is the one function that takes a resume claim, in one statement, so
every caller (``answer``, ``question_settle``, ``resume_claim``, ``claim_work``) follows
the same rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from amoeba.operations.steps.context import StepContext
from amoeba.operations.steps.limits import resume_claim_seconds
from amoeba.operations.steps.models import (
    ClaimStatus,
    ResumeClaimPayload,
    ResumeClaimReply,
    ResumeClaimRequest,
    ResumeReadReply,
    ResumeReadRequest,
    ResumeRecordReply,
    ResumeRecordRequest,
)
from amoeba.store import sql_local_work
from amoeba.store.answers import get_answer, record_resume
from amoeba.store.errors import StoreRowError
from amoeba.store.questions import get_question
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import ResumeOutcome


@dataclass(frozen=True)
class ResumeClaimed:
    """The caller holds the claim; ``claim_id`` goes with every later write of it."""

    claim_id: str


@dataclass(frozen=True)
class ResumeInFlight:
    """Another attempt holds a claim that has not run out."""


@dataclass(frozen=True)
class ResumeFinal:
    """The answer already has a final outcome (``resumed`` or ``not_delivered``)."""

    outcome: ResumeOutcome


def claim_resume(
    transaction: Transaction, answer_seq: int, now: datetime, limit_seconds: float
) -> ResumeClaimed | ResumeInFlight | ResumeFinal:
    """Take the resume claim for the answer, or say why not.

    Applies only when the outcome is not final and either no claim is held or the held
    one is ``limit_seconds`` old or older.

    Raises:
        StoreRowError: There is no answer with this ``seq``.
    """
    claim_id = uuid4().hex
    cutoff = encode_timestamp(now - timedelta(seconds=limit_seconds))
    cursor = transaction.execute(
        sql_local_work.CLAIM_RESUME,
        (
            encode_timestamp(now),
            claim_id,
            answer_seq,
            ResumeOutcome.REFUSED.value,
            cutoff,
        ),
    )
    if cursor.rowcount == 1:
        return ResumeClaimed(claim_id)
    answer = get_answer(transaction, answer_seq)
    if answer is None:
        raise StoreRowError(f"answer {answer_seq} does not exist to claim")
    outcome = answer.resume_outcome
    if outcome is ResumeOutcome.RESUMED or outcome is ResumeOutcome.NOT_DELIVERED:
        return ResumeFinal(outcome)
    return ResumeInFlight()


def claim_payload(
    transaction: Transaction, answer_seq: int, claim_id: str, resume_wait_seconds: float
) -> ResumeClaimPayload:
    """What a resume needs for the answer it holds the claim of.

    Raises:
        StoreRowError: The answer, or the question it answers, is not stored.
    """
    answer = get_answer(transaction, answer_seq)
    if answer is None:
        raise StoreRowError(f"answer {answer_seq} does not exist")
    question = get_question(transaction, answer.key)
    if question is None:
        raise StoreRowError(f"answer {answer_seq} has no question row")
    return ResumeClaimPayload(
        answer_seq=answer_seq,
        claim_id=claim_id,
        run_id=answer.key.run_id,
        paused_at=answer.key.paused_at,
        question=question.question,
        checkout=question.checkout,
        answer_text=answer.answer,
        resume_wait_seconds=resume_wait_seconds,
    )


def resume_claim(context: StepContext, request: ResumeClaimRequest) -> ResumeClaimReply:
    """The step ``resume_claim``: take the resume claim for an answer (D4, D6)."""
    config = context.require_config()
    claim = claim_resume(
        context.transaction,
        request.answer_seq,
        context.now,
        resume_claim_seconds(config),
    )
    match claim:
        case ResumeClaimed(claim_id=claim_id):
            payload = claim_payload(
                context.transaction,
                request.answer_seq,
                claim_id,
                float(config.resume_wait_seconds),
            )
            return ResumeClaimReply(status=ClaimStatus.CLAIMED, claim=payload)
        case ResumeInFlight():
            return ResumeClaimReply(status=ClaimStatus.IN_FLIGHT)
        case ResumeFinal():
            stored = get_answer(context.transaction, request.answer_seq)
            if stored is None:
                raise StoreRowError(f"answer {request.answer_seq} does not exist")
            return ResumeClaimReply(
                status=ClaimStatus.FINAL,
                final_outcome=claim.outcome,
                final_detail=stored.resume_detail,
                final_log=stored.resume_log,
            )


def resume_read(context: StepContext, request: ResumeReadRequest) -> ResumeReadReply:
    """The step ``resume_read``: the payload, when the claim id is still the answer's
    (D4). A claim that ran out and was taken again, or an outcome that was recorded
    and cleared it, reads as none."""
    config = context.require_config()
    answer = get_answer(context.transaction, request.answer_seq)
    if answer is None or answer.resume_claim_id != request.claim_id:
        return ResumeReadReply()
    payload = claim_payload(
        context.transaction,
        request.answer_seq,
        request.claim_id,
        float(config.resume_wait_seconds),
    )
    return ResumeReadReply(claim=payload)


def resume_record(
    context: StepContext, request: ResumeRecordRequest
) -> ResumeRecordReply:
    """The step ``resume_record``: write the outcome unless one is final and say what
    the store holds (D4, D6). Loads no config."""
    wrote = record_resume(
        context.transaction,
        request.answer_seq,
        request.outcome,
        detail=request.detail,
        log=request.log,
        at=context.now,
        claim_id=request.claim_id,
    )
    stored = get_answer(context.transaction, request.answer_seq)
    if stored is None or stored.resume_outcome is None:
        raise StoreRowError(
            f"answer {request.answer_seq} has no resume outcome to report"
        )
    return ResumeRecordReply(
        outcome=stored.resume_outcome,
        detail=stored.resume_detail,
        log=stored.resume_log,
        wrote=wrote,
    )
