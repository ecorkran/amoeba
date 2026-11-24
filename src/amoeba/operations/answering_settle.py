"""Settle a claim from what its answering run produced (slice 223, D6, D7).

``settle`` turns a finished run (or a start or wait that failed) into one move out of
``claimed``, one step: ``answered`` through the gate (run on the hub in one
transaction), or ``waiting_on_pm`` with the reason. Every move names the claim it
holds, so a PM answer that arrived meanwhile wins and the result is ``Superseded``.
The reads of ``answer.json`` and
``check.json`` come from the scratch directory, which is derived from the run id, so
a later call can settle a run whose first caller died. ``answer_claim`` is start,
wait and settle in order; no store transaction is open across a subprocess.
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.answering.artifacts import read_answer, read_check
from amoeba.answering.decide import (
    Confirmed,
    Declined,
    RunState,
    RunSummary,
    decide_answer,
)
from amoeba.answering.values import DeclineReason
from amoeba.operations.answering_run import (
    Claim,
    scratch_path,
    start,
    wait,
)
from amoeba.operations.deps import Deps
from amoeba.operations.steps.models import QUESTION_SETTLE, QUESTION_WAIT
from amoeba.operations.steps.models_pause import (
    EvidenceModel,
    QuestionSettleRequest,
    QuestionWaitRequest,
    SettleStatus,
)
from amoeba.operations.steps.models_resume import ResumeClaimPayload
from amoeba.operations.store_steps import Steps
from amoeba.upstream.squadron.run_outcome import Finished


@dataclass(frozen=True)
class Answered:
    """The claim settled as ``answered``; ``answer_seq`` is the answerer's row and
    ``claim`` the resume claim the hub took with it, which drives the resume."""

    answer_seq: int
    answer: str
    claim: ResumeClaimPayload


@dataclass(frozen=True)
class Waiting:
    """The claim settled as ``waiting_on_pm``."""

    reason: DeclineReason
    detail: str


@dataclass(frozen=True)
class Superseded:
    """The claim was no longer this caller's (a PM answer won, or another settle)."""


type SettleResult = Answered | Waiting | Superseded


def settle(
    steps: Steps, deps: Deps, claim: Claim, finished: Finished | Declined
) -> SettleResult:
    """Decide ``finished`` and make the one move out of ``claimed`` it calls for.

    The gate (the reserved-term screen and the answer limit) runs on the hub, inside
    the transaction that writes the answer (``question_settle``, 262 D1).
    """
    decision = _decide(deps, claim, finished)
    if isinstance(decision, Declined):
        return _wait_on_pm(steps, claim, decision)
    reply = steps.run(
        QUESTION_SETTLE,
        QuestionSettleRequest(
            run_id=claim.key.run_id,
            paused_at=claim.key.paused_at,
            answering_run_id=claim.answering_run_id,
            answer=decision.answer,
            cited=decision.cited,
            evidence=EvidenceModel.of(decision.evidence),
        ),
    )
    match reply.status:
        case SettleStatus.ANSWERED:
            if reply.answer_seq is None or reply.claim is None:
                raise AssertionError("an answered settle carries its seq and claim")
            return Answered(reply.answer_seq, decision.answer, reply.claim)
        case SettleStatus.SUPERSEDED:
            return Superseded()
        case SettleStatus.WAITING:
            if reply.reason is None or reply.detail is None:
                raise AssertionError("a waiting settle carries its reason and detail")
            return Waiting(reply.reason, reply.detail)


def _decide(
    deps: Deps, claim: Claim, finished: Finished | Declined
) -> Confirmed | Declined:
    """The decision on a finished run, reading its replies from the scratch."""
    if isinstance(finished, Declined):
        return finished
    summary = RunSummary.of(finished)
    if summary.state is not RunState.COMPLETED:
        return decide_answer(summary, None, None, claim.passage_ids)
    scratch = scratch_path(deps.answering_dir, claim.answering_run_id)
    return decide_answer(
        summary, read_answer(scratch), read_check(scratch), claim.passage_ids
    )


def _wait_on_pm(steps: Steps, claim: Claim, declined: Declined) -> Waiting | Superseded:
    moved = steps.run(
        QUESTION_WAIT,
        QuestionWaitRequest(
            run_id=claim.key.run_id,
            paused_at=claim.key.paused_at,
            answering_run_id=claim.answering_run_id,
            reason=declined.reason,
            detail=declined.detail,
            evidence=EvidenceModel.of(declined.evidence),
        ),
    )
    if not moved.applied:
        return Superseded()
    return Waiting(declined.reason, declined.detail)


def answer_claim(steps: Steps, deps: Deps, claim: Claim) -> SettleResult:
    """Start the claim's answering run, wait for it and settle it.

    The scratch directory is already made (it is part of the claim). A start or wait
    that fails settles the claim as waiting, with its reason.
    """
    scratch = scratch_path(deps.answering_dir, claim.answering_run_id)
    child = start(deps, claim.answering_run_id, scratch, claim.settings)
    if isinstance(child, Declined):
        return settle(steps, deps, claim, child)
    finished = wait(deps, child, claim.answering_run_id, claim.wait_seconds)
    return settle(steps, deps, claim, finished)
