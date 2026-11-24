"""``question_settle``: the answerer's answer through the gate, on the hub (262 D1, D4).

The gate (the reserved-term screen and the answer limit) runs inside the transaction
that writes the answer, so two settles for one run cannot both pass the limit. The hub
builds it from its own config and the member's settings, so no client config is read.
"""

from __future__ import annotations

from amoeba.answering.gate import evaluate_gate
from amoeba.answering.values import DeclineReason, GateRefusal
from amoeba.operations.member_answering import answering_for
from amoeba.operations.steps.context import StepContext
from amoeba.operations.steps.limits import resume_claim_seconds
from amoeba.operations.steps.models_pause import (
    QuestionSettleReply,
    QuestionSettleRequest,
    SettleStatus,
)
from amoeba.operations.steps.resume import ResumeClaimed, claim_payload, claim_resume
from amoeba.store.answers import Lost, Settled, settle_answered_in
from amoeba.store.errors import StoreRowError
from amoeba.store.models import QuestionKey
from amoeba.store.programs import get_member
from amoeba.store.questions import get_question, settle_waiting
from amoeba.upstream.bounded_text import cut_to_bound


def question_settle(
    context: StepContext, request: QuestionSettleRequest
) -> QuestionSettleReply:
    """Answered: write the answer and take its resume claim. Refused by the gate:
    ``waiting_on_pm`` with the reason. Claim gone: superseded."""
    config = context.require_config()
    transaction = context.transaction
    key = QuestionKey(request.run_id, request.paused_at)
    row = get_question(transaction, key)
    if row is None:
        return QuestionSettleReply(status=SettleStatus.SUPERSEDED)
    member = get_member(transaction, row.member_id)
    if member is None:
        raise StoreRowError(f"question {key} names member {row.member_id}, not stored")
    settings = answering_for(member.settings, config).settings

    def gate(prior: int) -> GateRefusal | None:
        return evaluate_gate(
            row.question, prior, answer=request.answer, settings=settings
        )

    outcome = settle_answered_in(
        transaction,
        key,
        request.answering_run_id,
        answer=request.answer,
        cited=request.cited,
        evidence=request.evidence.to_evidence(),
        gate=gate,
        now=context.now,
    )
    if isinstance(outcome, Lost):
        return QuestionSettleReply(status=SettleStatus.SUPERSEDED)
    if isinstance(outcome, Settled):
        claim = claim_resume(
            transaction, outcome.answer_seq, context.now, resume_claim_seconds(config)
        )
        if not isinstance(claim, ResumeClaimed):
            raise StoreRowError(
                f"the new answer {outcome.answer_seq} was not claimable"
            )
        payload = claim_payload(
            transaction,
            outcome.answer_seq,
            claim.claim_id,
            float(config.resume_wait_seconds),
        )
        return QuestionSettleReply(
            status=SettleStatus.ANSWERED, answer_seq=outcome.answer_seq, claim=payload
        )
    detail = _refusal_detail(outcome, settings.answer_limit, key)
    moved = settle_waiting(
        transaction,
        key,
        request.answering_run_id,
        reason=outcome.reason,
        detail=detail,
        evidence=request.evidence.to_evidence(),
        now=context.now,
    )
    if not moved:
        return QuestionSettleReply(status=SettleStatus.SUPERSEDED)
    return QuestionSettleReply(
        status=SettleStatus.WAITING, reason=outcome.reason, detail=detail
    )


def _refusal_detail(refusal: GateRefusal, answer_limit: int, key: QuestionKey) -> str:
    if refusal.reason is DeclineReason.RESERVED_TERM:
        return cut_to_bound(
            f"the question or the answer mentions the reserved term "
            f"{refusal.reserved_term!r}"
        )
    return f"{answer_limit} automatic answers were already given for run {key.run_id}"
