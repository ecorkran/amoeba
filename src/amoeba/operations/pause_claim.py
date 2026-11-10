"""Claiming a question and running its answering run (slice 223, D4, D6, D7).

``start_new_claim`` is the path for a question no row exists for: gather the context,
make the scratch, insert the row (``claimed``, or ``waiting_on_pm`` with the failure),
then run the answering run and settle it. ``restart_dead_claim`` is the D7 path for a
claimant that died before it spawned. ``finish`` turns a settle into a result,
resuming the run only for an ``answered`` question. Claiming comes after context and
scratch, so no claim exists without its run id or a failure reason; no store
transaction is open across a subprocess.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from amoeba.answering.decide import sources_reason
from amoeba.answering.inputs import QuestionInput
from amoeba.answering.launch import discard_scratch
from amoeba.answering.passages import SourcesProblem
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
    waiting_result,
)
from amoeba.store.answers import automatic_answer_count
from amoeba.store.questions import (
    NewQuestion,
    insert_question,
    replace_claim,
    settle_waiting,
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
class _Failed:
    reason: DeclineReason
    detail: str
    #: What was gathered before the failure, when anything was.
    context: PauseContext | None


def start_new_claim(
    store: Store, config: UserConfig, deps: Deps, target: PauseTarget
) -> HandlePauseResult:
    """Claim a question no row exists for, answer it, and resume the run if answered."""
    answering = answering_for(target.member.settings, config)
    with store.read() as transaction:
        given = automatic_answer_count(transaction, target.key.run_id)
    limit = answering.settings.answer_limit
    if given >= limit:
        detail = f"{given} automatic answers were already given for this run"
        return _record_waiting(
            store,
            deps,
            target,
            _Failed(DeclineReason.ANSWER_LIMIT_REACHED, detail, None),
        )
    prepared = _prepare(store, deps, target, answering)
    if isinstance(prepared, _Failed):
        return _record_waiting(store, deps, target, prepared)
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


def restart_dead_claim(
    store: Store,
    config: UserConfig,
    deps: Deps,
    target: PauseTarget,
    old_answering_run_id: str,
) -> HandlePauseResult:
    """D7, a claimant that died before it spawned: gather again, swap the claim to a
    new run id and scratch, and run it."""
    answering = answering_for(target.member.settings, config)
    prepared = _prepare(store, deps, target, answering)
    if isinstance(prepared, _Failed):
        return _settle_dead_claim_waiting(
            store, deps, target, old_answering_run_id, prepared
        )
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
    return _run(store, config, deps, target, answering, prepared)


def _prepare(
    store: Store, deps: Deps, target: PauseTarget, answering: MemberAnswering
) -> _Prepared | _Failed:
    """Gather the context, mint the run id and make the scratch."""
    settings = answering.settings
    context = gather(
        store, target.checkout, target.member, target.run_facts, settings, deps.cf_run
    )
    if isinstance(context, SourcesProblem):
        return _Failed(sources_reason(context), cut_to_bound(context.detail), None)
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
        return _Failed(
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


def _record_waiting(
    store: Store, deps: Deps, target: PauseTarget, failed: _Failed
) -> HandlePauseResult:
    """Insert the question as ``waiting_on_pm`` with the failure that stopped it."""
    context = failed.context
    new = NewQuestion(
        key=target.key,
        member_id=target.member.project_id,
        question=target.question,
        checkout=str(target.checkout),
        slice_label=None if context is None else context.slice_label,
        source_commit=None if context is None else context.source_commit,
        passages=None if context is None else context.refs,
        answering_run_id=None,
        waiting_reason=failed.reason,
        waiting_detail=failed.detail,
    )
    with store.write() as transaction:
        inserted = insert_question(transaction, new, now=deps.clock())
    if not inserted:
        return skipped(SkipReason.ALREADY_CLAIMED, target.key, str(target.checkout))
    return waiting_result(target, failed.reason, failed.detail, None)


def _settle_dead_claim_waiting(
    store: Store,
    deps: Deps,
    target: PauseTarget,
    old_answering_run_id: str,
    failed: _Failed,
) -> HandlePauseResult:
    """A dead claim whose context cannot be gathered again waits on the PM."""
    with store.write() as transaction:
        moved = settle_waiting(
            transaction,
            target.key,
            old_answering_run_id,
            reason=failed.reason,
            detail=failed.detail,
            evidence=None,
            now=deps.clock(),
        )
    if not moved:
        return superseded_result(target, old_answering_run_id)
    return waiting_result(target, failed.reason, failed.detail, old_answering_run_id)
