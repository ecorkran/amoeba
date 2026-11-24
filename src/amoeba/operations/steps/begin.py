"""``pause_begin``: everything ``handle-pause`` reads from the store before it gathers,
in one write transaction (262 D4, D5).

Steps 1 to 7 of D4: close the run's older open questions on the calling machine, run
the message sweep when due, stop on a pause the run alone decides or an answering run's
own, find the caller, read the row and its latest answer, and, by what the row is, the
question's request link, or its held request and the answer limit.
"""

from __future__ import annotations

from amoeba.config.user_config import UserConfig
from amoeba.operations.caller import NotAProject, NotInProgram, find_caller
from amoeba.operations.errors import MALFORMED_CALL, CallRefused
from amoeba.operations.member_answering import answering_for
from amoeba.operations.pause_models import SkipReason
from amoeba.operations.pause_observed import (
    ObservedPause,
    claim_is_stale,
    classify_run_only,
    run_only_skip,
)
from amoeba.operations.question_judge import RunFate, SweepResult, judge_in
from amoeba.operations.request_link import BadLink, Link, find_request_link
from amoeba.operations.steps.context import StepContext
from amoeba.operations.steps.limits import pause_claim_seconds
from amoeba.operations.steps.models_pause import (
    LimitResult,
    PauseBeginReply,
    PauseBeginRequest,
)
from amoeba.operations.steps.pause import request_facts
from amoeba.store.answers import automatic_answer_count, latest_answer
from amoeba.store.errors import StoreRowError
from amoeba.store.machines import acting_machine_id, question_machine
from amoeba.store.message_sweep import sweep, sweep_due
from amoeba.store.messages import get_message
from amoeba.store.models import Member, QuestionKey, QuestionRecord
from amoeba.store.question_closing import open_rows_of_run_on_machine
from amoeba.store.questions import any_answering_run_id, get_question
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import MessageKind, QuestionState


def pause_begin(context: StepContext, request: PauseBeginRequest) -> PauseBeginReply:
    """The step ``pause_begin``.

    Raises:
        CallRefused: ``malformed_call``: the run alone does not decide the skip and
            the request names no caller.
    """
    config = context.require_config()
    transaction = context.transaction
    swept = _sweep(context, config, request)
    observed = ObservedPause(
        request.paused, request.checkpoint_kind, request.paused_at, request.question
    )
    early = classify_run_only(observed)
    if early is not None:
        reason, detail = run_only_skip(early, request.outcome, request.checkpoint_kind)
        return PauseBeginReply(swept=swept, skip=reason, skip_detail=detail)
    if any_answering_run_id(transaction, request.run_id):
        return PauseBeginReply(swept=swept, skip=SkipReason.ANSWERING_RUN)
    if request.here is None:
        raise CallRefused(MALFORMED_CALL, "pause_begin needs here past the run's skip")
    paused_at, question = observed.paused_at, observed.question
    if paused_at is None or question is None:
        raise AssertionError("classify_run_only passed a pause without its text")
    found = find_caller(transaction, acting_machine_id(transaction), request.here)
    if isinstance(found, NotAProject):
        return PauseBeginReply(
            swept=swept,
            skip=SkipReason.NOT_A_PROJECT,
            skip_detail=found.message or None,
        )
    if isinstance(found, NotInProgram):
        return PauseBeginReply(swept=swept, not_in_program=found.cf_id)
    return _for_member(
        context, config, swept, found, QuestionKey(request.run_id, paused_at), question
    )


def _sweep(
    context: StepContext, config: UserConfig, request: PauseBeginRequest
) -> SweepResult:
    """Steps 1 and 2: the run's older rows on this machine, then the message sweep."""
    transaction = context.transaction
    swept = SweepResult()
    fate = request.fate
    if fate is not None:
        run_fate = RunFate(fate.reason, fate.detail, fate.current_paused_at)
        rows = open_rows_of_run_on_machine(
            transaction, request.run_id, acting_machine_id(transaction)
        )
        judged = [
            (row, run_fate)
            for row in rows
            if row.key.paused_at != run_fate.current_paused_at
        ]
        swept = judge_in(transaction, config, judged, context.now)
    if sweep_due(transaction, context.now, config.prune_after_days):
        sweep(transaction, context.now, config.prune_after_days)
    return swept


def _for_member(  # noqa: PLR0913 - the pieces of steps 5 to 7
    context: StepContext,
    config: UserConfig,
    swept: SweepResult,
    member: Member,
    key: QuestionKey,
    question: str,
) -> PauseBeginReply:
    transaction = context.transaction
    answering = answering_for(member.settings, config)
    row = get_question(transaction, key)
    base = PauseBeginReply(
        swept=swept,
        member=member,
        answering=answering,
        answering_wait_seconds=float(config.answering_wait_seconds),
        resume_wait_seconds=float(config.resume_wait_seconds),
        prune_after_days=config.prune_after_days,
        row=row,
    )
    limit = answering.settings.answer_limit
    if row is None:
        return _without_row(context, base, member, key, question, limit)
    where = question_machine(transaction, key.run_id, key.paused_at)
    other = None
    if where is not None and where.machine_id != acting_machine_id(transaction):
        other = where.name or REMOVED_MACHINE_NAME
    latest = (
        latest_answer(transaction, key) if row.state is QuestionState.ANSWERED else None
    )
    return base.model_copy(
        update={
            "claim_stale": claim_is_stale(
                row, context.now, pause_claim_seconds(config)
            ),
            "other_machine": other,
            "latest_answer": latest,
            **_held_part(context, row, key, limit),
        }
    )


#: Named in the ``other_machine`` skip for a row whose machine was removed.
REMOVED_MACHINE_NAME = "a machine that was removed"


def _limit(transaction: Transaction, run_id: str, answer_limit: int) -> LimitResult:
    given = automatic_answer_count(transaction, run_id)
    return LimitResult(given=given, reached=given >= answer_limit)


def _without_row(  # noqa: PLR0913 - the pieces of step 6
    context: StepContext,
    base: PauseBeginReply,
    member: Member,
    key: QuestionKey,
    question: str,
    answer_limit: int,
) -> PauseBeginReply:
    """Step 6: the question's request link, and whether the answer limit is reached."""
    transaction = context.transaction

    def resolve(candidate: str) -> bool:
        message = get_message(transaction, candidate)
        return (
            message is not None
            and message.kind is MessageKind.REQUEST
            and message.from_member == member.project_id
        )

    link = find_request_link(question, resolve)
    update: dict[str, object] = {"limit": _limit(transaction, key.run_id, answer_limit)}
    if isinstance(link, Link):
        update["link_request_id"] = link.request_id
    elif isinstance(link, BadLink):
        update["link_problem"] = link.detail
    return base.model_copy(update=update)


def _held_part(
    context: StepContext, row: QuestionRecord, key: QuestionKey, answer_limit: int
) -> dict[str, object]:
    """Step 7: a held row's request, its result when done, and the answer limit."""
    if row.state is not QuestionState.WAITING_ON_REQUEST:
        return {}
    if row.request_id is None:
        raise StoreRowError(f"held question {key} has no request_id")
    return {
        "request": request_facts(context.transaction, row.request_id, context.now),
        "limit": _limit(context.transaction, key.run_id, answer_limit),
    }
