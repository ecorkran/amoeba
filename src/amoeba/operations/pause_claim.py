"""Claiming a question and running its answering run (slice 223, D4, D6, D7).

``start_new_claim`` is the path for a question no row exists for: gather the context,
make the scratch, insert the row (``claimed``, or ``waiting_on_pm`` with the failure),
then run the answering run and settle it. ``start_held_claim`` is its counterpart for
a question held on a request that is now done (242 D6): the request's result is one
more passage, and the claim updates the held row instead of inserting one.
``restart_dead_claim`` is the D7 path for a claimant that died before it spawned.
``finish`` turns a settle into a result, resuming the run only for an ``answered``
question. Claiming comes after context and scratch, so no claim exists without its
run id or a failure reason; each store move is one step, so no transaction is open
across a subprocess (262 D5).
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
from amoeba.operations.answering_run import (
    Claim,
    ScratchFailure,
    make_scratch,
    scratch_path,
)
from amoeba.operations.answering_settle import answer_claim
from amoeba.operations.claim_waiting import (
    ClaimFailed,
    record_waiting,
    settle_dead_claim_waiting,
    settle_held,
    with_request,
)
from amoeba.operations.deps import Deps
from amoeba.operations.member_answering import MemberAnswering
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
from amoeba.operations.steps.models import (
    PAUSE_SOURCES,
    QUESTION_CLAIM_HELD,
    QUESTION_INSERT,
    QUESTION_REPLACE_CLAIM,
)
from amoeba.operations.steps.models_pause import (
    HeldRequestModel,
    LossKind,
    PauseBeginReply,
    PauseSourcesReply,
    PauseSourcesRequest,
    QuestionClaimHeldRequest,
    QuestionInsertRequest,
    QuestionReplaceClaimRequest,
    passages_to_models,
)
from amoeba.operations.store_steps import Steps
from amoeba.store.errors import StoreRowError
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


def held_request_of(model: HeldRequestModel) -> HeldRequest:
    """A ``done`` request's fields, as the hub's step returned them."""
    return HeldRequest(
        request_id=model.request_id,
        replied_by=model.replied_by,
        done_at=model.done_at,
        result=model.result,
        commit=model.commit,
        version=model.version,
    )


def _answering(begun: PauseBeginReply) -> MemberAnswering:
    if begun.answering is None:
        raise AssertionError("pause_begin returns the answering settings for a member")
    return begun.answering


def start_new_claim(
    steps: Steps, deps: Deps, target: PauseTarget, begun: PauseBeginReply
) -> HandlePauseResult:
    """Claim a question no row exists for, answer it, and resume the run if answered."""
    answering = _answering(begun)
    limited = _limit_reached(begun)
    if limited is not None:
        return record_waiting(steps, target, limited)
    prepared = _prepare(deps, target, answering, _sources(steps, target))
    if isinstance(prepared, ClaimFailed):
        return record_waiting(steps, target, prepared)
    inserted = steps.run(
        QUESTION_INSERT,
        QuestionInsertRequest(
            run_id=target.key.run_id,
            paused_at=target.key.paused_at,
            member_id=target.member.project_id,
            question=target.question,
            checkout=str(target.checkout),
            slice_label=prepared.context.slice_label,
            source_commit=prepared.context.source_commit,
            passages=passages_to_models(prepared.context.refs),
            answering_run_id=prepared.answering_run_id,
            waiting_reason=None,
            waiting_detail=None,
        ),
    )
    if not inserted.inserted:
        discard_scratch(prepared.scratch)
        return skipped(SkipReason.ALREADY_CLAIMED, target.key, str(target.checkout))
    return _run(steps, deps, target, begun, prepared)


def start_held_claim(  # noqa: PLR0913 - the held claim and its request, D6
    steps: Steps,
    deps: Deps,
    target: PauseTarget,
    begun: PauseBeginReply,
    request: HeldRequest,
) -> HandlePauseResult:
    """D6: claim a held question whose request is done, answer it from the request's
    result and the ordinary passages, and resume the run if answered."""
    answering = _answering(begun)
    request_id = request.request_id
    limited = _limit_reached(begun)
    if limited is not None:
        return settle_held(steps, target, request_id, limited)
    prepared = _prepare(deps, target, answering, _sources(steps, target), request)
    if isinstance(prepared, ClaimFailed):
        return settle_held(steps, target, request_id, prepared)
    claimed = steps.run(
        QUESTION_CLAIM_HELD,
        QuestionClaimHeldRequest(
            run_id=target.key.run_id,
            paused_at=target.key.paused_at,
            answering_run_id=prepared.answering_run_id,
            passages=passages_to_models(prepared.context.refs) or (),
            slice_label=prepared.context.slice_label,
            source_commit=prepared.context.source_commit,
        ),
    )
    if not claimed.claimed:
        discard_scratch(prepared.scratch)
        if claimed.lost_to is LossKind.CLAIM:
            lost = skipped(SkipReason.ALREADY_CLAIMED, target.key, str(target.checkout))
        else:
            lost = superseded_result(target, None)
        return with_request(lost, request_id)
    result = _run(steps, deps, target, begun, prepared)
    return with_request(result, request_id)


def restart_dead_claim(  # noqa: PLR0913 - the dead claim and its request, D7
    steps: Steps,
    deps: Deps,
    target: PauseTarget,
    begun: PauseBeginReply,
    old_answering_run_id: str,
    request_id: str | None = None,
) -> HandlePauseResult:
    """D7, a claimant that died before it spawned: gather again, swap the claim to a
    new run id and scratch, and run it. A claim that came from a held question
    (``request_id``) gets its request's passage again (242 D6)."""
    answering = _answering(begun)
    sources = _sources(steps, target, request_id)
    request_or_failure = _request_of(sources, request_id)
    prepared = (
        request_or_failure
        if isinstance(request_or_failure, ClaimFailed)
        else _prepare(deps, target, answering, sources, request_or_failure)
    )
    if isinstance(prepared, ClaimFailed):
        result = settle_dead_claim_waiting(
            steps, target, old_answering_run_id, prepared
        )
        return result if request_id is None else with_request(result, request_id)
    swapped = steps.run(
        QUESTION_REPLACE_CLAIM,
        QuestionReplaceClaimRequest(
            run_id=target.key.run_id,
            paused_at=target.key.paused_at,
            old_answering_run_id=old_answering_run_id,
            new_answering_run_id=prepared.answering_run_id,
            passages=passages_to_models(prepared.context.refs) or (),
        ),
    )
    if not swapped.applied:
        discard_scratch(prepared.scratch)
        return skipped(SkipReason.ALREADY_CLAIMED, target.key, str(target.checkout))
    result = _run(steps, deps, target, begun, prepared)
    return result if request_id is None else with_request(result, request_id)


def _limit_reached(begun: PauseBeginReply) -> ClaimFailed | None:
    """The answer-limit check both claim paths make first, from the result
    ``pause_begin`` computed on the hub; ``None`` under the limit."""
    if begun.limit is None:
        raise AssertionError("pause_begin returns the limit for a claim path")
    if not begun.limit.reached:
        return None
    detail = f"{begun.limit.given} automatic answers were already given for this run"
    return ClaimFailed(DeclineReason.ANSWER_LIMIT_REACHED, detail, None)


def _sources(
    steps: Steps, target: PauseTarget, request_id: str | None = None
) -> PauseSourcesReply:
    """What the gather reads from the store: one read step."""
    return steps.run(
        PAUSE_SOURCES,
        PauseSourcesRequest(member_id=target.member.project_id, request_id=request_id),
    )


def _request_of(
    sources: PauseSourcesReply, request_id: str | None
) -> HeldRequest | ClaimFailed | None:
    """The request a dead held claim came from; ``request_unknown`` once pruned."""
    if request_id is None:
        return None
    facts = sources.request
    if facts is None:
        raise AssertionError("pause_sources returns the request it was asked for")
    if facts.state is None:
        detail = f"request {request_id} is no longer stored"
        return ClaimFailed(DeclineReason.REQUEST_UNKNOWN, detail, None)
    if facts.held is None:
        raise StoreRowError(f"request {request_id} has no result to answer from")
    return held_request_of(facts.held)


def _prepare(  # noqa: PLR0913 - the pieces of one gather
    deps: Deps,
    target: PauseTarget,
    answering: MemberAnswering,
    sources: PauseSourcesReply,
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
        sources,
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
    steps: Steps,
    deps: Deps,
    target: PauseTarget,
    begun: PauseBeginReply,
    prepared: _Prepared,
) -> HandlePauseResult:
    if begun.answering_wait_seconds is None:
        raise AssertionError("pause_begin returns the answering wait for a member")
    claim = Claim(
        key=target.key,
        answering_run_id=prepared.answering_run_id,
        question=target.question,
        passage_ids=prepared.context.passages.ids,
        settings=_answering(begun).settings,
        wait_seconds=begun.answering_wait_seconds,
    )
    settled = answer_claim(steps, deps, claim)
    return finish(steps, deps, target, prepared.answering_run_id, settled)
