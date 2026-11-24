"""The question claim steps' hub side (262 D4): each wraps today's store call and its
compare-and-set, with the hub's clock. A caller that loses starts no answering run."""

from __future__ import annotations

from datetime import datetime

from amoeba.operations.steps.context import StepContext
from amoeba.operations.steps.models_pause import (
    AppliedReply,
    HeldRequestModel,
    InsertedReply,
    LossKind,
    QuestionClaimHeldReply,
    QuestionClaimHeldRequest,
    QuestionHoldReply,
    QuestionHoldRequest,
    QuestionInsertRequest,
    QuestionReplaceClaimRequest,
    QuestionWaitRequest,
    RequestFacts,
    passages_from_models,
)
from amoeba.store.errors import StoreRowError
from amoeba.store.held_questions import (
    HeldQuestion,
    claim_held,
    insert_held,
    settle_held_waiting,
)
from amoeba.store.messages import effective_state, get_message
from amoeba.store.models import QuestionKey
from amoeba.store.questions import (
    NewQuestion,
    get_question,
    insert_question,
    replace_claim,
    settle_waiting,
)
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import RequestState


def request_facts(
    transaction: Transaction, request_id: str, now: datetime
) -> RequestFacts:
    """The request's effective state on the hub's clock, and its result once ``done``.

    Raises:
        StoreRowError: A ``done`` request with no addressee or result.
    """
    message = get_message(transaction, request_id)
    if message is None:
        return RequestFacts(request_id=request_id, state=None)
    state = effective_state(message, now)
    held = None
    if state is RequestState.DONE:
        if message.to_member is None or message.result is None:
            raise StoreRowError(f"request {request_id} has no addressee or result")
        held = HeldRequestModel(
            request_id=request_id,
            replied_by=message.to_member,
            done_at=message.state_changed_at,
            result=message.result,
            commit=message.result_commit,
            version=message.result_version,
        )
    return RequestFacts(
        request_id=request_id, state=state, reason=message.reason, held=held
    )


def question_insert(
    context: StepContext, request: QuestionInsertRequest
) -> InsertedReply:
    """Insert the row, as ``claimed`` or ``waiting_on_pm``, on the acting machine."""
    new = NewQuestion(
        key=QuestionKey(request.run_id, request.paused_at),
        member_id=request.member_id,
        question=request.question,
        checkout=request.checkout,
        slice_label=request.slice_label,
        source_commit=request.source_commit,
        passages=passages_from_models(request.passages),
        answering_run_id=request.answering_run_id,
        waiting_reason=request.waiting_reason,
        waiting_detail=request.waiting_detail,
    )
    inserted = insert_question(context.transaction, new, now=context.now)
    return InsertedReply(inserted=inserted)


def question_hold(
    context: StepContext, request: QuestionHoldRequest
) -> QuestionHoldReply:
    """Insert the held row and say what state its request is in now."""
    held = HeldQuestion(
        QuestionKey(request.run_id, request.paused_at),
        request.member_id,
        request.question,
        request.checkout,
    )
    inserted = insert_held(context.transaction, held, request.request_id, context.now)
    if not inserted:
        return QuestionHoldReply(inserted=False)
    facts = request_facts(context.transaction, request.request_id, context.now)
    return QuestionHoldReply(inserted=True, request=facts)


def question_claim_held(
    context: StepContext, request: QuestionClaimHeldRequest
) -> QuestionClaimHeldReply:
    """``waiting_on_request -> claimed``; on a loss, who won: a claim or an answer."""
    key = QuestionKey(request.run_id, request.paused_at)
    passages = passages_from_models(request.passages)
    if passages is None:
        raise AssertionError("the request requires its passages")
    claimed = claim_held(
        context.transaction,
        key,
        answering_run_id=request.answering_run_id,
        passages=passages,
        slice_label=request.slice_label,
        source_commit=request.source_commit,
        now=context.now,
    )
    if claimed:
        return QuestionClaimHeldReply(claimed=True)
    current = get_question(context.transaction, key)
    # Only a claim sets the answering run: another caller claimed it first. Otherwise
    # a PM answer or a dismissal ended the hold.
    won = current is not None and current.answering_run_id is not None
    return QuestionClaimHeldReply(
        claimed=False, lost_to=LossKind.CLAIM if won else LossKind.ENDED
    )


def question_replace_claim(
    context: StepContext, request: QuestionReplaceClaimRequest
) -> AppliedReply:
    """Swap a dead claim's answering run, only while the row is still claimed by the
    run id the request names."""
    passages = passages_from_models(request.passages)
    if passages is None:
        raise AssertionError("the request requires its passages")
    swapped = replace_claim(
        context.transaction,
        QuestionKey(request.run_id, request.paused_at),
        old_answering_run_id=request.old_answering_run_id,
        new_answering_run_id=request.new_answering_run_id,
        passages=passages,
        now=context.now,
    )
    return AppliedReply(applied=swapped)


def question_wait(context: StepContext, request: QuestionWaitRequest) -> AppliedReply:
    """Move the named claim, or a held row, to ``waiting_on_pm`` with its reason."""
    key = QuestionKey(request.run_id, request.paused_at)
    if request.answering_run_id is None:
        moved = settle_held_waiting(
            context.transaction,
            key,
            reason=request.reason,
            detail=request.detail,
            now=context.now,
        )
        return AppliedReply(applied=moved)
    evidence = None if request.evidence is None else request.evidence.to_evidence()
    moved = settle_waiting(
        context.transaction,
        key,
        request.answering_run_id,
        reason=request.reason,
        detail=request.detail,
        evidence=evidence,
        now=context.now,
    )
    return AppliedReply(applied=moved)
