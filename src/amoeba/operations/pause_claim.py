"""Claiming a question and running its answering run (slice 223, D4, D6, D7).

``start_new_claim`` is the path for a question no row exists for: gather the context,
make the scratch, insert the row (``claimed``, or ``waiting_on_pm`` with the failure),
then run the answering run and settle it. ``start_held_claim`` is its counterpart for
a question held on a request that is now done (242 D6): the request's result is one
more passage, and the claim updates the held row instead of inserting one.
``restart_dead_claim`` is the D7 path for a claimant that died before it spawned.
``finish`` turns a settle into a result, resuming the run only for an ``answered``
question. Claiming comes after context and scratch, so no claim exists without its
run id or a failure reason; no store transaction is open across a subprocess.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from amoeba.answering.decide import sources_reason
from amoeba.answering.inputs import QuestionInput
from amoeba.answering.launch import discard_scratch
from amoeba.answering.passages import SourcesProblem
from amoeba.answering.request_passage import request_passage
from amoeba.answering.values import DeclineReason
from amoeba.config.user_config import UserConfig
from amoeba.operations.answering_run import (
    Claim,
    ScratchFailure,
    make_scratch,
    scratch_path,
)
from amoeba.operations.answering_settle import (
    answer_claim,
)
from amoeba.operations.claim_waiting import (
    ClaimFailed,
    record_waiting,
    settle_dead_claim_waiting,
    settle_held,
    with_request,
)
from amoeba.operations.deps import Deps
from amoeba.operations.member_answering import MemberAnswering, answering_for
from amoeba.operations.pause_context import PauseContext, gather
from amoeba.operations.pause_models import (
    HandlePauseResult,
    SkipReason,
)
from amoeba.operations.pause_results import (
    PauseTarget,
    finish,
    skipped,
    superseded_result,
)
from amoeba.store.answers import automatic_answer_count
from amoeba.store.held_questions import claim_held
from amoeba.store.messages import get_message
from amoeba.store.models import Message
from amoeba.store.questions import (
    NewQuestion,
    get_question,
    insert_question,
    replace_claim,
)
from amoeba.store.store import Store
from amoeba.upstream.bounded_text import cut_to_bound
from amoeba.upstream.squadron.launch import mint_run_id


@dataclass(frozen=True)
class _Prepared:
    context: PauseContext
    answering_run_id: str
    scratch: Path


@dataclass(frozen=True)
class HeldRequest:
    """The plain fields of a ``done`` request that ``request_passage`` takes."""

    request_id: str
    replied_by: str
    done_at: datetime
    result: str
    commit: str | None
    version: str | None


def held_request_of(message: Message) -> HeldRequest:
    """A ``done`` request's fields. Raises ``ValueError`` for a row with no
    addressee or result, which a ``done`` request always has."""
    if message.to_member is None or message.result is None:
        raise ValueError(f"request {message.message_id} has no addressee or result")
    return HeldRequest(
        request_id=message.message_id,
        replied_by=message.to_member,
        done_at=message.state_changed_at,
        result=message.result,
        commit=message.result_commit,
        version=message.result_version,
    )


def start_new_claim(
    store: Store, config: UserConfig, deps: Deps, target: PauseTarget
) -> HandlePauseResult:
    """Claim a question no row exists for, answer it, and resume the run if answered."""
    answering = answering_for(target.member.settings, config)
    limited = _limit_reached(store, target, answering)
    if limited is not None:
        return record_waiting(store, deps, target, limited)
    prepared = _prepare(store, deps, target, answering)
    if isinstance(prepared, ClaimFailed):
        return record_waiting(store, deps, target, prepared)
    new = NewQuestion(
        key=target.key,
        member_id=target.member.project_id,
        question=target.question,
        checkout=str(target.checkout),
        slice_label=prepared.context.slice_label,
        source_commit=prepared.context.source_commit,
        passages=prepared.context.refs,
        answering_run_id=prepared.answering_run_id,
        waiting_reason=None,
        waiting_detail=None,
    )
    with store.write() as transaction:
        inserted = insert_question(transaction, new, now=deps.clock())
    if not inserted:
        discard_scratch(prepared.scratch)
        return skipped(SkipReason.ALREADY_CLAIMED, target.key, str(target.checkout))
    return _run(store, config, deps, target, answering, prepared)


def start_held_claim(
    store: Store,
    config: UserConfig,
    deps: Deps,
    target: PauseTarget,
    request: HeldRequest,
) -> HandlePauseResult:
    """D6: claim a held question whose request is done, answer it from the request's
    result and the ordinary passages, and resume the run if answered."""
    answering = answering_for(target.member.settings, config)
    request_id = request.request_id
    limited = _limit_reached(store, target, answering)
    if limited is not None:
        return settle_held(store, deps, target, request_id, limited)
    prepared = _prepare(store, deps, target, answering, request)
    if isinstance(prepared, ClaimFailed):
        return settle_held(store, deps, target, request_id, prepared)
    with store.write() as transaction:
        claimed = claim_held(
            transaction,
            target.key,
            answering_run_id=prepared.answering_run_id,
            passages=prepared.context.refs,
            slice_label=prepared.context.slice_label,
            source_commit=prepared.context.source_commit,
            now=deps.clock(),
        )
        current = None if claimed else get_question(transaction, target.key)
    if not claimed:
        discard_scratch(prepared.scratch)
        # Only a claim sets the answering run: another caller claimed it first.
        # Otherwise a PM answer or a dismissal ended the hold.
        if current is not None and current.answering_run_id is not None:
            lost = skipped(SkipReason.ALREADY_CLAIMED, target.key, str(target.checkout))
        else:
            lost = superseded_result(target, None)
        return with_request(lost, request_id)
    result = _run(store, config, deps, target, answering, prepared)
    return with_request(result, request_id)


def restart_dead_claim(  # noqa: PLR0913 - the dead claim and its request, D7
    store: Store,
    config: UserConfig,
    deps: Deps,
    target: PauseTarget,
    old_answering_run_id: str,
    request_id: str | None = None,
) -> HandlePauseResult:
    """D7, a claimant that died before it spawned: gather again, swap the claim to a
    new run id and scratch, and run it. A claim that came from a held question
    (``request_id``) gets its request's passage again (242 D6)."""
    answering = answering_for(target.member.settings, config)
    request_or_failure = _read_request(store, request_id)
    prepared = (
        request_or_failure
        if isinstance(request_or_failure, ClaimFailed)
        else _prepare(store, deps, target, answering, request_or_failure)
    )
    if isinstance(prepared, ClaimFailed):
        result = settle_dead_claim_waiting(
            store, deps, target, old_answering_run_id, prepared
        )
        return result if request_id is None else with_request(result, request_id)
    with store.write() as transaction:
        swapped = replace_claim(
            transaction,
            target.key,
            old_answering_run_id=old_answering_run_id,
            new_answering_run_id=prepared.answering_run_id,
            passages=prepared.context.refs,
            now=deps.clock(),
        )
    if not swapped:
        discard_scratch(prepared.scratch)
        return skipped(SkipReason.ALREADY_CLAIMED, target.key, str(target.checkout))
    result = _run(store, config, deps, target, answering, prepared)
    return result if request_id is None else with_request(result, request_id)


def _limit_reached(
    store: Store, target: PauseTarget, answering: MemberAnswering
) -> ClaimFailed | None:
    """The answer-limit check both claim paths make first; ``None`` under the limit."""
    with store.read() as transaction:
        given = automatic_answer_count(transaction, target.key.run_id)
    if given < answering.settings.answer_limit:
        return None
    detail = f"{given} automatic answers were already given for this run"
    return ClaimFailed(DeclineReason.ANSWER_LIMIT_REACHED, detail, None)


def _read_request(
    store: Store, request_id: str | None
) -> HeldRequest | ClaimFailed | None:
    """The request a dead held claim came from; ``request_unknown`` once pruned."""
    if request_id is None:
        return None
    with store.read() as transaction:
        message = get_message(transaction, request_id)
    if message is None:
        detail = f"request {request_id} is no longer stored"
        return ClaimFailed(DeclineReason.REQUEST_UNKNOWN, detail, None)
    return held_request_of(message)


def _prepare(
    store: Store,
    deps: Deps,
    target: PauseTarget,
    answering: MemberAnswering,
    request: HeldRequest | None = None,
) -> _Prepared | ClaimFailed:
    """Gather the context (with the request's passage, when one is given), mint the
    run id and make the scratch."""
    settings = answering.settings
    passage = None
    if request is not None:
        passage = request_passage(
            request.request_id,
            request.replied_by,
            request.done_at,
            request.result,
            request.commit,
            request.version,
        )
    context = gather(
        store,
        target.checkout,
        target.member,
        target.run_facts,
        settings,
        deps.cf_run,
        cf_project_id=target.cf_project_id,
        request=passage,
    )
    if isinstance(context, SourcesProblem):
        return ClaimFailed(sources_reason(context), cut_to_bound(context.detail), None)
    run_id = mint_run_id(deps.clock())
    made = make_scratch(
        deps.answering_dir,
        run_id,
        QuestionInput(context.slice_label, target.question),
        context.passages_markdown,
        settings.max_cost_usd,
        answering.not_authorized,
    )
    if isinstance(made, ScratchFailure):
        discard_scratch(scratch_path(deps.answering_dir, run_id))
        return ClaimFailed(
            DeclineReason.ANSWERING_LAUNCH_FAILED, cut_to_bound(made.detail), context
        )
    return _Prepared(context, run_id, made)


def _run(  # noqa: PLR0913 - the pieces a claimed question needs to run
    store: Store,
    config: UserConfig,
    deps: Deps,
    target: PauseTarget,
    answering: MemberAnswering,
    prepared: _Prepared,
) -> HandlePauseResult:
    claim = Claim(
        key=target.key,
        answering_run_id=prepared.answering_run_id,
        question=target.question,
        passage_ids=prepared.context.passages.ids,
        settings=answering.settings,
        wait_seconds=config.answering_wait_seconds,
    )
    settled = answer_claim(store, deps, claim)
    return finish(store, config, deps, target, prepared.answering_run_id, settled)
