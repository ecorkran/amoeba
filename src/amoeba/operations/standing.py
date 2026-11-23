"""``standing``: record a ruling the PM gave ahead of time (slice 230, D2, D10).

The document is validated here, so the CLI and the MCP layer pass their input through
unchanged. ``--member`` is a member's name or id, found in the store (261 D6); no ``cf``
runs. The lookup of the program or member and the give are one transaction, so a repeat
of the same call finds the row the first one wrote.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import ValidationError

from amoeba.operations.caller import find_member
from amoeba.operations.reject_codes import validation_problems
from amoeba.operations.standing_fit import overflow
from amoeba.operations.standing_models import (
    StandingOutcome,
    StandingRejection,
    StandingRequest,
    StandingResult,
)
from amoeba.store.programs import get_program
from amoeba.store.standing import give_standing
from amoeba.store.store import Store
from amoeba.store.vocabulary import StandingReach


def standing(
    store: Store,
    document: object,
    *,
    max_chars: int,
    now: datetime,
) -> StandingResult:
    """Give the standing answer ``document`` describes, or find the same one active.

    ``max_chars`` is the config's ``passages_max_chars``. A new row that would take
    the rendered standing answers reaching any member past it is refused as
    ``too_long`` and rolled back, rather than found at the next pause.

    Raises:
        StoreError: The store cannot be used; nothing was written.
    """
    try:
        request = StandingRequest.model_validate(document)
    except ValidationError as error:
        return StandingResult.rejected(
            StandingRejection.MALFORMED, validation_problems(error)
        )
    reach = _reach(request)
    try:
        return _give(store, request, reach, max_chars, now)
    except _Overflow as refused:
        return StandingResult.rejected(StandingRejection.TOO_LONG, (str(refused),))


class _Overflow(Exception):
    """Raised inside the write transaction so the inserted row is rolled back."""


def _give(  # noqa: PLR0913 - the request and what standing resolved for it
    store: Store,
    request: StandingRequest,
    reach: StandingReach,
    max_chars: int,
    now: datetime,
) -> StandingResult:
    with store.write() as transaction:
        member_id: str | None = None
        if request.member is not None:
            member = find_member(transaction, request.member)
            if member is None:
                return _no_such_member(request.member)
            member_id = member.project_id
        if request.program is not None and (
            get_program(transaction, request.program) is None
        ):
            return StandingResult.rejected(
                StandingRejection.NO_SUCH_PROGRAM,
                (f"no program {request.program}",),
            )
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
