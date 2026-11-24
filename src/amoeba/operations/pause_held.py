"""A question held on a request its repo sent (slice 242, D1, D3, D4).

``link_of`` reads the question's ``amoeba-request`` marker from what ``pause_begin``
resolved on the hub. ``hold_new`` records a new question that has one: held for a
resolved id (then evaluated at once, so a request done before the pause and one done
after it take the same code), or waiting on the PM as ``request_unknown`` for a marker
that resolves to nothing. Both evaluate the request by its effective state. A ``done``
request goes to ``pause_claim.start_held_claim``; no claim, scratch or dead-claim logic
lives here.
"""

from __future__ import annotations

from typing import Final

from amoeba.answering.values import DeclineReason
from amoeba.operations.claim_waiting import (
    ClaimFailed,
    record_waiting,
    settle_held,
    with_request,
)
from amoeba.operations.deps import Deps
from amoeba.operations.pause_claim import held_request_of, start_held_claim
from amoeba.operations.pause_models import (
    HandlePauseOutcome,
    HandlePauseResult,
    SkipReason,
)
from amoeba.operations.pause_results import PauseTarget, skipped
from amoeba.operations.request_link import BadLink, Link, LinkResult, NoLink
from amoeba.operations.steps.models import QUESTION_HOLD
from amoeba.operations.steps.models_pause import (
    PauseBeginReply,
    QuestionHoldRequest,
    RequestFacts,
)
from amoeba.operations.store_steps import Steps
from amoeba.store.errors import StoreRowError
from amoeba.store.models import QuestionRecord
from amoeba.store.vocabulary import RequestState
from amoeba.upstream.bounded_text import cut_to_bound

#: The request states a held question keeps waiting through.
STILL_WAITING: Final = frozenset({RequestState.OPEN, RequestState.ACCEPTED})
#: A request that ended without a result, and the reason its question waits with.
ENDED_WITHOUT_RESULT: Final = {
    RequestState.DECLINED: DeclineReason.REQUEST_DECLINED,
    RequestState.CANCELLED: DeclineReason.REQUEST_CANCELLED,
    RequestState.EXPIRED: DeclineReason.REQUEST_EXPIRED,
}
NO_REASON_DETAIL: Final = "the request ended with no reason"


def link_of(begun: PauseBeginReply) -> LinkResult:
    """The question's link as ``pause_begin`` resolved it on the hub: an id counts
    only if it is a request the question's member sent (D1)."""
    if begun.link_request_id is not None:
        return Link(begun.link_request_id)
    if begun.link_problem is not None:
        return BadLink(begun.link_problem)
    return NoLink()


def hold_new(
    steps: Steps,
    deps: Deps,
    target: PauseTarget,
    begun: PauseBeginReply,
    link: Link | BadLink,
) -> HandlePauseResult:
    """Record a new question that carries a marker, then evaluate a held one."""
    if isinstance(link, BadLink):
        failed = ClaimFailed(
            DeclineReason.REQUEST_UNKNOWN, cut_to_bound(link.detail), None
        )
        return record_waiting(steps, target, failed)
    held = steps.run(
        QUESTION_HOLD,
        QuestionHoldRequest(
            run_id=target.key.run_id,
            paused_at=target.key.paused_at,
            member_id=target.member.project_id,
            question=target.question,
            checkout=str(target.checkout),
            request_id=link.request_id,
        ),
    )
    if not held.inserted or held.request is None:
        lost = skipped(SkipReason.ALREADY_CLAIMED, target.key, str(target.checkout))
        return with_request(lost, link.request_id)
    return _evaluate(steps, deps, target, begun, held.request)


def handle_held(
    steps: Steps,
    deps: Deps,
    target: PauseTarget,
    begun: PauseBeginReply,
    row: QuestionRecord,
) -> HandlePauseResult:
    """The D4 table for a ``waiting_on_request`` row, from the request state
    ``pause_begin`` returned."""
    if row.request_id is None:
        raise StoreRowError(f"held question {row.key} has no request_id")
    if begun.request is None:
        raise AssertionError("pause_begin returns the request of a held row")
    return _evaluate(steps, deps, target, begun, begun.request)


def _evaluate(
    steps: Steps,
    deps: Deps,
    target: PauseTarget,
    begun: PauseBeginReply,
    request: RequestFacts,
) -> HandlePauseResult:
    request_id = request.request_id
    state = request.state
    if state is None:
        detail = (
            f"the request was pruned after prune_after_days "
            f"({begun.prune_after_days} days); its result is no longer stored"
        )
        failed = ClaimFailed(DeclineReason.REQUEST_UNKNOWN, detail, None)
        return settle_held(steps, target, request_id, failed)
    if state in STILL_WAITING:
        return HandlePauseResult(
            HandlePauseOutcome.HELD,
            detail=state.value,
            key=target.key,
            checkout=str(target.checkout),
            request_id=request_id,
        )
    if state is RequestState.DONE:
        if request.held is None:
            raise StoreRowError(f"request {request_id} is done with no result")
        return start_held_claim(
            steps, deps, target, begun, held_request_of(request.held)
        )
    detail = NO_REASON_DETAIL if not request.reason else cut_to_bound(request.reason)
    failed = ClaimFailed(ENDED_WITHOUT_RESULT[state], detail, None)
    return settle_held(steps, target, request_id, failed)
