"""``changes``: what the caller's providers reported since a time (slice 227, D3).

Writes nothing and keeps no read marker (D4): the caller owns its starting point. The
names come from one ``cf`` call and the member from another, both before the one read
transaction, so no subprocess runs under it.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from amoeba.operations.changes_models import (
    ChangesOutcome,
    ChangesRequest,
    ChangesResult,
    ChangesWarning,
    ChangesWarningCode,
    MemberRef,
    ProviderPair,
)
from amoeba.operations.deps import Deps
from amoeba.operations.members import ContextForgeError
from amoeba.operations.release_member import resolve_release_member
from amoeba.operations.report_release_models import (
    ReleaseProblem,
    ReleaseReport,
    malformed_problems,
)
from amoeba.store.programs import pairs_consumed_by
from amoeba.store.releases import visible_releases
from amoeba.store.store import Store
from amoeba.upstream.context_forge.cli_call import CfCallFailed

__all__ = ["ChangesResult", "changes"]


def changes(
    store: Store, document: object, *, directory: Path, deps: Deps
) -> ChangesResult:
    """The reports of the providers of the member whose checkout is ``directory``.

    Raises:
        ContextForgeError: ``cf`` gave no project names or no project for the
            directory.
        StoreError: The store cannot be used.
    """
    try:
        request = ChangesRequest.model_validate(document)
    except ValidationError as error:
        return _rejected(None, malformed_problems(error))
    names = deps.project_names()
    if isinstance(names, CfCallFailed):
        raise ContextForgeError(names.detail)
    member = resolve_release_member(store, directory, deps.cf_run)
    if isinstance(member, ReleaseProblem):
        return _rejected(request.since, (member,))
    with store.read() as transaction:
        own_pairs = pairs_consumed_by(transaction, member.project_id)
        pairs = tuple(
            ProviderPair(
                provider=MemberRef(
                    id=pair.provider_id, name=names.get(pair.provider_id)
                ),
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
    caller = MemberRef(id=member.project_id, name=names.get(member.project_id))
    return ChangesResult(
        outcome=ChangesOutcome.LISTED,
        member=caller,
        since=request.since,
        pairs=pairs,
        problems=(),
        warnings=_warnings(caller, pairs),
    )


def _warnings(
    caller: MemberRef, pairs: tuple[ProviderPair, ...]
) -> tuple[ChangesWarning, ...]:
    """One warning per listed id Context Forge does not name, the caller first."""
    unnamed = (
        ref.id
        for ref in (caller, *(pair.provider for pair in pairs))
        if ref.name is None
    )
    return tuple(
        ChangesWarning(
            code=ChangesWarningCode.NOT_IN_CONTEXT_FORGE,
            detail=f"Context Forge lists no project named for {project_id}",
        )
        for project_id in dict.fromkeys(unnamed)
    )


def _rejected(since: str | None, problems: tuple[ReleaseProblem, ...]) -> ChangesResult:
    return ChangesResult(
        outcome=ChangesOutcome.REJECTED,
        member=None,
        since=since,
        pairs=(),
        problems=problems,
        warnings=(),
    )
