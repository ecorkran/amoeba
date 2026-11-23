"""``standing``: record a ruling the PM gave ahead of time (slice 230, D2, D10).

The document is validated here, so the CLI and the MCP layer pass their input through
unchanged. ``--member`` is resolved by the caller's resolver (``cf`` locally), before
the write transaction opens, so no subprocess runs while the write lock is held. The
lookup of the program or member and the give are then one transaction, so a repeat
of the same call finds the row the first one wrote.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from pydantic import ValidationError

from amoeba.operations.reject_codes import validation_problems
from amoeba.operations.standing_fit import overflow
from amoeba.operations.standing_models import (
    StandingOutcome,
    StandingRejection,
    StandingRequest,
    StandingResult,
)
from amoeba.store.programs import get_member, get_program
from amoeba.store.standing import give_standing
from amoeba.store.store import Store
from amoeba.store.vocabulary import StandingReach

#: Resolves ``--member`` to a member id, or ``None`` when no active member goes by
#: that reference. The local way asks Context Forge; the hub takes only an id (260 D11).
type MemberResolver = Callable[[str], str | None]


def standing(
    store: Store,
    document: object,
    *,
    max_chars: int,
    resolve_member: MemberResolver,
    now: datetime,
) -> StandingResult:
    """Give the standing answer ``document`` describes, or find the same one active.

    ``max_chars`` is the config's ``passages_max_chars``. A new row that would take
    the rendered standing answers reaching any member past it is refused as
    ``too_long`` and rolled back, rather than found at the next pause.

    Raises:
        ContextForgeError: The local resolver's ``cf`` failed; nothing was written.
        StoreError: The store cannot be used; nothing was written.
    """
    try:
        request = StandingRequest.model_validate(document)
    except ValidationError as error:
        return StandingResult.rejected(
            StandingRejection.MALFORMED, validation_problems(error)
        )
    member_id = None if request.member is None else resolve_member(request.member)
    if request.member is not None and member_id is None:
        return _no_such_member(request.member)
    reach = _reach(request)
    try:
        return _give(store, request, reach, member_id, max_chars, now)
    except _Overflow as refused:
        return StandingResult.rejected(StandingRejection.TOO_LONG, (str(refused),))


class _Overflow(Exception):
    """Raised inside the write transaction so the inserted row is rolled back."""


def _give(  # noqa: PLR0913 - the request and what standing resolved for it
    store: Store,
    request: StandingRequest,
    reach: StandingReach,
    member_id: str | None,
    max_chars: int,
    now: datetime,
) -> StandingResult:
    with store.write() as transaction:
        if request.program is not None and (
            get_program(transaction, request.program) is None
        ):
            return StandingResult.rejected(
                StandingRejection.NO_SUCH_PROGRAM,
                (f"no program {request.program}",),
            )
        if member_id is not None and get_member(transaction, member_id) is None:
            return _no_such_member(request.member)
        standing_id, created = give_standing(
            transaction, request.text, reach, request.program, member_id, now
        )
        problem = (
            overflow(transaction, reach, request.program, member_id, max_chars)
            if created
            else None
        )
        if problem is not None:
            raise _Overflow(problem)
    return StandingResult(
        outcome=StandingOutcome.GIVEN if created else StandingOutcome.UNCHANGED,
        standing_id=standing_id,
        reach=reach,
        program=request.program,
        member=member_id,
    )


def _reach(request: StandingRequest) -> StandingReach:
    if request.program is not None:
        return StandingReach.PROGRAM
    if request.member is not None:
        return StandingReach.MEMBER
    return StandingReach.ALL


def _no_such_member(member: str | None) -> StandingResult:
    return StandingResult.rejected(
        StandingRejection.NO_SUCH_MEMBER, (f"{member} is not an active member",)
    )
