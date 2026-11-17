"""A question held on a request its repo sent (slice 242, D1, D3, D4).

``link_for`` reads the question's ``amoeba-request`` marker against the store.
``hold_new`` records a new question that has one: held for a resolved id (then
``handle_held`` at once, so a request done before the pause and one done after it take
the same code), or waiting on the PM as ``request_unknown`` for a marker that resolves
to nothing. ``handle_held`` is the one evaluation path, by the request's effective
state. A ``done`` request goes to ``pause_claim.start_held_claim``; no claim, scratch
or dead-claim logic lives here.
"""

from __future__ import annotations

from typing import Final

from amoeba.answering.values import DeclineReason
from amoeba.config.user_config import UserConfig
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
from amoeba.operations.request_link import BadLink, Link, LinkResult, find_request_link
from amoeba.store.errors import StoreRowError
from amoeba.store.held_questions import HeldQuestion, insert_held
from amoeba.store.messages import effective_state, get_message
from amoeba.store.models import QuestionRecord
from amoeba.store.store import Store
from amoeba.store.vocabulary import MessageKind, RequestState
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


def link_for(store: Store, target: PauseTarget) -> LinkResult:
    """The question's link: an id counts only if it is a request the question's
    member sent (D1). One read transaction."""
    member_id = target.member.project_id
    with store.read() as transaction:

        def resolve(candidate: str) -> bool:
            message = get_message(transaction, candidate)
            return (
                message is not None
                and message.kind is MessageKind.REQUEST
                and message.from_member == member_id
            )

        return find_request_link(target.question, resolve)


def hold_new(
    store: Store,
    config: UserConfig,
    deps: Deps,
    target: PauseTarget,
    link: Link | BadLink,
) -> HandlePauseResult:
    """Record a new question that carries a marker, then evaluate a held one."""
    if isinstance(link, BadLink):
        failed = ClaimFailed(
            DeclineReason.REQUEST_UNKNOWN, cut_to_bound(link.detail), None
        )
        return record_waiting(store, deps, target, failed)
    held = HeldQuestion(
        target.key, target.member.project_id, target.question, str(target.checkout)
    )
    with store.write() as transaction:
        inserted = insert_held(transaction, held, link.request_id, deps.clock())
    if not inserted:
        lost = skipped(SkipReason.ALREADY_CLAIMED, target.key, str(target.checkout))
        return with_request(lost, link.request_id)
    return _evaluate(store, config, deps, target, link.request_id)


def handle_held(
    store: Store,
    config: UserConfig,
    deps: Deps,
    target: PauseTarget,
    row: QuestionRecord,
) -> HandlePauseResult:
    """The D4 table for a ``waiting_on_request`` row."""
    if row.request_id is None:
        raise StoreRowError(f"held question {row.key} has no request_id")
    return _evaluate(store, config, deps, target, row.request_id)


def _evaluate(
    store: Store,
    config: UserConfig,
    deps: Deps,
    target: PauseTarget,
    request_id: str,
) -> HandlePauseResult:
    with store.read() as transaction:
        message = get_message(transaction, request_id)
    if message is None:
        detail = (
            f"the request was pruned after prune_after_days "
            f"({config.prune_after_days} days); its result is no longer stored"
        )
        failed = ClaimFailed(DeclineReason.REQUEST_UNKNOWN, detail, None)
        return settle_held(store, deps, target, request_id, failed)
    state = effective_state(message, deps.clock())
    if state is None:
        raise StoreRowError(f"held question {target.key} names note {request_id}")
    if state in STILL_WAITING:
        return HandlePauseResult(
            HandlePauseOutcome.HELD,
            detail=state.value,
            key=target.key,
            checkout=str(target.checkout),
            request_id=request_id,
        )
    if state is RequestState.DONE:
        request = held_request_of(message)
        return start_held_claim(store, config, deps, target, request)
    detail = NO_REASON_DETAIL if not message.reason else cut_to_bound(message.reason)
    failed = ClaimFailed(ENDED_WITHOUT_RESULT[state], detail, None)
    return settle_held(store, deps, target, request_id, failed)
