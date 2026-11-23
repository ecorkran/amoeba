"""``changes``: what the caller's providers reported since a time (slice 227, D3).

Writes nothing and keeps no read marker (D4): the caller owns its starting point.
Names come from the store; no ``cf`` runs here.
"""

from __future__ import annotations

from pydantic import ValidationError

from amoeba.operations.changes_models import (
    ChangesOutcome,
    ChangesRequest,
    ChangesResult,
    MemberRef,
    ProviderPair,
)
from amoeba.operations.deps import Deps
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.release_member import resolve_release_member
from amoeba.operations.report_release_models import (
    ReleaseProblem,
    ReleaseReport,
    malformed_problems,
)
from amoeba.store.programs import get_member_any, pairs_consumed_by
from amoeba.store.releases import visible_releases
from amoeba.store.store import Store, Transaction

__all__ = ["ChangesResult", "changes"]


def changes(
    store: Store, document: object, *, here: HereCaller | HereNotAProject, deps: Deps
) -> ChangesResult:
    """The reports of the providers of the member whose checkout is ``here``.

    Raises:
        StoreError: The store cannot be used.
    """
    try:
        request = ChangesRequest.model_validate(document)
    except ValidationError as error:
        return _rejected(None, malformed_problems(error))
    member = resolve_release_member(store, here)
    if isinstance(member, ReleaseProblem):
        return _rejected(request.since, (member,))
    with store.read() as transaction:
        own_pairs = pairs_consumed_by(transaction, member.project_id)
        pairs = tuple(
            ProviderPair(
                provider=_ref(transaction, pair.provider_id),
                consumed=pair.consumed,
                releases=tuple(
                    ReleaseReport.from_release(release)
                    for release in visible_releases(
                        transaction, pair.provider_id, pair.consumed, request.since
                    )
                ),
            )
            for pair in own_pairs
        )
        caller = _ref(transaction, member.project_id)
    return ChangesResult(
        outcome=ChangesOutcome.LISTED,
        member=caller,
        since=request.since,
        pairs=pairs,
        problems=(),
        warnings=(),
    )


def _ref(transaction: Transaction, member_id: str) -> MemberRef:
    """The member as its id and the name the store holds for it (261 D13)."""
    member = get_member_any(transaction, member_id)
    if member is None:
        raise ValueError(f"member {member_id!r} is in a pair but not in the store")
    return MemberRef(id=member_id, name=member.name)


def _rejected(since: str | None, problems: tuple[ReleaseProblem, ...]) -> ChangesResult:
    return ChangesResult(
        outcome=ChangesOutcome.REJECTED,
        member=None,
        since=since,
        pairs=(),
        problems=problems,
        warnings=(),
    )
