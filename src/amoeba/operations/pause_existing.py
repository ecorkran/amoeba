"""A question that already has a row: settled paths and the dead claim
(slice 223, D3, D4, D7).

``answered`` with an answer not yet handed over resumes with the recorded answer and
starts no answering run. ``waiting_on_pm`` and handed-over answers are skipped. A
``claimed`` row is decided by the claim's answering run and the claim's age
(``updated_at``: the insert, or the last ``replace_claim``) against
``answering_wait_seconds``. Squadron failing to say is an operational error with
nothing written.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.answering.decide import Declined
from amoeba.answering.values import AnsweringEvidence, DeclineReason
from amoeba.operations.answering_run import Claim
from amoeba.operations.answering_settle import settle
from amoeba.operations.deps import Deps
from amoeba.operations.pause_claim import restart_dead_claim
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.pause_held import handle_held
from amoeba.operations.pause_models import HandlePauseResult, SkipReason
from amoeba.operations.pause_results import (
    PauseTarget,
    finish,
    resume_answer,
    skipped,
)
from amoeba.operations.steps.models_pause import PauseBeginReply
from amoeba.operations.store_steps import Steps
from amoeba.store.errors import StoreRowError
from amoeba.store.models import AnswerRecord, QuestionRecord
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.run_outcome import (
    PollFailure,
    RunEnded,
    RunOutcome,
)

#: An answering run that has ended, one way or another: the claimant died before it
#: could settle, so the settle is done from the scratch (D7).
_ENDED = frozenset(
    {
        RunOutcome.COMPLETED,
        RunOutcome.FAILED,
        RunOutcome.PAUSED,
        RunOutcome.ORPHANED,
    }
)


def handle_existing(  # noqa: PLR0913 - the pieces of one classified pause
    steps: Steps,
    deps: Deps,
    target: PauseTarget,
    begun: PauseBeginReply,
    existing: QuestionRecord,
    pause_class: PauseClass,
    latest: AnswerRecord | None,
) -> HandlePauseResult:
    """The path for a question that has a row, by its ``classify_pause`` class."""
    checkout = str(target.checkout)
    match pause_class:
        case PauseClass.ANSWERED_UNRESUMED:
            if latest is None:
                raise StoreRowError(f"question {target.key} has no answer row")
            return resume_answer(
                steps,
                deps,
                target.key,
                existing.checkout,
                latest.seq,
                existing.answering_run_id,
            )
        case PauseClass.SETTLED:
            return skipped(SkipReason.SETTLED, target.key, checkout)
        case PauseClass.CLOSED:
            closed = existing.closed_reason
            return skipped(
                SkipReason.CLOSED,
                target.key,
                checkout,
                None if closed is None else str(closed),
            )
        case PauseClass.WAITING_ON_PM:
            reason = existing.waiting_reason
            return skipped(
                SkipReason.WAITING_ON_PM,
                target.key,
                checkout,
                None if reason is None else str(reason),
            )
        case PauseClass.WAITING_ON_REQUEST:
            return handle_held(steps, deps, target, begun, existing)
        case PauseClass.CLAIM_LIVE | PauseClass.CLAIM_STALE:
            old = pause_class is PauseClass.CLAIM_STALE
            return _claimed(steps, deps, target, begun, existing, old=old)
        case _:
            raise ValueError(f"{pause_class} is not a class of a question with a row")


def _claimed(  # noqa: PLR0913 - the pieces of one D7 row
    steps: Steps,
    deps: Deps,
    target: PauseTarget,
    begun: PauseBeginReply,
    existing: QuestionRecord,
    *,
    old: bool,
) -> HandlePauseResult:
    """The dead-claim table of D7. ``old`` is the claim's age against the limit, as
    ``classify_pause`` judged it."""
    answering_run_id = existing.answering_run_id
    if answering_run_id is None or existing.passages is None:
        raise StoreRowError(f"claimed question {target.key} has no run id or passages")
    polled = deps.poll_run(answering_run_id)
    if isinstance(polled, PollFailure):
        raise SquadronError(polled.reason)
    if begun.answering is None or begun.answering_wait_seconds is None:
        raise AssertionError("pause_begin returns the answering settings for a member")
    wait_seconds = begun.answering_wait_seconds
    claim = Claim(
        key=target.key,
        answering_run_id=answering_run_id,
        question=target.question,
        passage_ids=frozenset(ref.id for ref in existing.passages),
        settings=begun.answering.settings,
        wait_seconds=wait_seconds,
    )
    if polled.outcome in _ENDED:
        settled = settle(steps, deps, claim, RunEnded(polled))
        return finish(steps, deps, target, answering_run_id, settled)
    if polled.outcome is RunOutcome.TIMED_OUT:
        return _running(steps, deps, target, claim, old)
    if polled.outcome is RunOutcome.NOT_FOUND:
        if not old:
            return skipped(SkipReason.ALREADY_CLAIMED, target.key, str(target.checkout))
        return restart_dead_claim(
            steps, deps, target, begun, answering_run_id, existing.request_id
        )
    raise SquadronError(
        f"answering run {answering_run_id} reads as {polled.outcome.value}"
    )


def _running(  # noqa: PLR0913 - the pieces of one D7 row
    steps: Steps,
    deps: Deps,
    target: PauseTarget,
    claim: Claim,
    old: bool,
) -> HandlePauseResult:
    """The answering run is still going: young is someone else's, old is stalled."""
    if not old:
        return skipped(SkipReason.ALREADY_CLAIMED, target.key, str(target.checkout))
    stalled = Declined(
        DeclineReason.ANSWERING_RUN_STALLED,
        f"no result after {claim.wait_seconds:g} seconds",
        AnsweringEvidence(),
    )
    settled = settle(steps, deps, claim, stalled)
    return finish(steps, deps, target, claim.answering_run_id, settled)


def checkout_of(existing: QuestionRecord) -> Path:
    """The checkout a question was claimed in."""
    return Path(existing.checkout)
