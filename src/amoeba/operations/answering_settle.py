"""Settle a claim from what its answering run produced (slice 223, D6, D7).

``settle`` turns a finished run (or a start or wait that failed) into one move out of
``claimed``: ``answered`` through the gate in one transaction, or ``waiting_on_pm``
with the reason. Every move names the claim it holds, so a PM answer that arrived
meanwhile wins and the result is ``Superseded``. The reads of ``answer.json`` and
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
from amoeba.answering.gate import evaluate_gate
from amoeba.answering.values import DeclineReason, GateRefusal
from amoeba.operations.answering_run import (
    Claim,
    scratch_path,
    start,
    wait,
)
from amoeba.operations.deps import Deps
from amoeba.store.answers import Lost, Settled, settle_answered
from amoeba.store.questions import settle_waiting
from amoeba.store.store import Store
from amoeba.upstream.bounded_text import cut_to_bound
from amoeba.upstream.squadron.run_outcome import Finished


@dataclass(frozen=True)
class Answered:
    """The claim settled as ``answered``; ``answer_seq`` is the answerer's row."""

    answer_seq: int
    answer: str


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
    store: Store, deps: Deps, claim: Claim, finished: Finished | Declined
) -> SettleResult:
    """Decide ``finished`` and make the one move out of ``claimed`` it calls for."""
    decision = _decide(deps, claim, finished)
    if isinstance(decision, Declined):
        return _wait_on_pm(store, deps, claim, decision)

    def gate(prior: int) -> GateRefusal | None:
        return evaluate_gate(
            claim.question, prior, answer=decision.answer, settings=claim.settings
        )

    outcome = settle_answered(
        store,
        claim.key,
        claim.answering_run_id,
        answer=decision.answer,
        cited=decision.cited,
        evidence=decision.evidence,
        gate=gate,
        now=deps.clock(),
    )
    if isinstance(outcome, Settled):
        return Answered(outcome.answer_seq, decision.answer)
    if isinstance(outcome, Lost):
        return Superseded()
    return _wait_on_pm(
        store,
        deps,
        claim,
        Declined(
            outcome.reason,
            _refusal_detail(outcome, claim),
            decision.evidence,
        ),
    )


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


def _wait_on_pm(
    store: Store, deps: Deps, claim: Claim, declined: Declined
) -> Waiting | Superseded:
    with store.write() as transaction:
        moved = settle_waiting(
            transaction,
            claim.key,
            claim.answering_run_id,
            reason=declined.reason,
            detail=declined.detail,
            evidence=declined.evidence,
            now=deps.clock(),
        )
    if not moved:
        return Superseded()
    return Waiting(declined.reason, declined.detail)


def _refusal_detail(refusal: GateRefusal, claim: Claim) -> str:
    if refusal.reason is DeclineReason.RESERVED_TERM:
        return cut_to_bound(
            f"the question or the answer mentions the reserved term "
            f"{refusal.reserved_term!r}"
        )
    return (
        f"{claim.settings.answer_limit} automatic answers were already given "
        f"for run {claim.key.run_id}"
    )


def answer_claim(store: Store, deps: Deps, claim: Claim) -> SettleResult:
    """Start the claim's answering run, wait for it and settle it.

    The scratch directory is already made (it is part of the claim). A start or wait
    that fails settles the claim as waiting, with its reason.
    """
    scratch = scratch_path(deps.answering_dir, claim.answering_run_id)
    child = start(deps, claim.answering_run_id, scratch, claim.settings)
    if isinstance(child, Declined):
        return settle(store, deps, claim, child)
    finished = wait(deps, child, claim.answering_run_id, claim.wait_seconds)
    return settle(store, deps, claim, finished)
