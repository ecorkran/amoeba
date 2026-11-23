"""Placing the runs of the ``runs`` document under members (slice 224, D4; 261, D11).

Rules, in order, by a run's directory lookup in the document: no directory and a missing
directory are unplaced; a failed lookup is unplaced; then the directory's Context Forge
project decides: not a project, or one that is no checkout of a member in scope, is
dropped, and the member whose checkout has that project id on the calling machine is
placed. Only a ``paused`` run is ever listed as unplaced: another status with nowhere to
go cannot be a missed hook and would bury what the PM has to act on. The document's
runs are already without answering scratch runs, and this module reads no disk and runs
no ``cf``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from amoeba.operations.runs_document import LookupKind, OpenRun
from amoeba.operations.status_models import UnplacedReason, UnplacedRunEntry
from amoeba.store.models import Member

__all__ = ["PlacedRun", "Placement", "UnplacedReason", "place_runs"]


@dataclass(frozen=True)
class PlacedRun:
    """A listed run and the member whose repo it runs in."""

    run: OpenRun
    member: Member


@dataclass(frozen=True)
class Placement:
    """Where the document's runs went. Dropped runs are in neither list."""

    placed: tuple[PlacedRun, ...]
    unplaced: tuple[UnplacedRunEntry, ...]


#: The lookups that leave a run with no member, and why.
_UNPLACED_REASONS = {
    LookupKind.NO_DIRECTORY: UnplacedReason.NO_DIRECTORY,
    LookupKind.DIRECTORY_MISSING: UnplacedReason.DIRECTORY_MISSING,
    LookupKind.FAILED: UnplacedReason.LOOKUP_FAILED,
}


def place_runs(
    runs: Sequence[OpenRun], members_by_checkout: Mapping[str, Member]
) -> Placement:
    """Place ``runs`` under the members in ``members_by_checkout`` (by the Context Forge
    project id of a checkout on the calling machine); see the module docstring."""
    placed: list[PlacedRun] = []
    unplaced: list[UnplacedRunEntry] = []
    for run in runs:
        lookup = run.lookup
        reason = _UNPLACED_REASONS.get(lookup.kind)
        if reason is not None:
            if run.is_paused:
                unplaced.append(_unplaced(run, reason, lookup.detail))
        elif lookup.kind is LookupKind.PROJECT:
            if lookup.project_id is None:
                raise ValueError(f"run {run.run_id} has a project lookup with no id")
            member = members_by_checkout.get(lookup.project_id)
            if member is not None:
                placed.append(PlacedRun(run, member))
    return Placement(tuple(placed), tuple(unplaced))


def _unplaced(
    run: OpenRun, reason: UnplacedReason, detail: str | None
) -> UnplacedRunEntry:
    checkpoint = run.checkpoint
    return UnplacedRunEntry(
        run_id=run.run_id,
        status=run.status,
        reason=reason,
        checkpoint_kind=None if checkpoint is None else checkpoint.kind,
        detail=detail,
    )
