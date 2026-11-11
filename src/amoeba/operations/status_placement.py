"""Placing the runs of ``sq runs list`` under members (slice 224, D4).

Rules, in order, by a run's ``working_directory``: ``None`` and a missing directory are
unplaced; a scratch directory of an answering run is dropped (no ``cf`` call); then the
directory's Context Forge project decides: not a project or not in scope is dropped, a
failed lookup is unplaced, a member in scope is placed. Only a ``paused`` run is ever
listed as unplaced: another status with nowhere to go cannot be a missed hook and would
bury what the PM has to act on. ``project_of`` is called once per directory.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from amoeba.operations.status_models import UnplacedReason, UnplacedRunEntry
from amoeba.store.models import Member
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.context_forge.project_of import CFProject, CFProjectNotFound
from amoeba.upstream.squadron.run_list import ListedRun

__all__ = ["PlacedRun", "Placement", "UnplacedReason", "place_runs"]

#: Looks up a directory's Context Forge project (one ``cf`` call).
type ProjectOf = Callable[[Path], CFProject | CFProjectNotFound | CfCallFailed]


@dataclass(frozen=True)
class PlacedRun:
    """A listed run and the member whose repo it runs in."""

    run: ListedRun
    member: Member


@dataclass(frozen=True)
class Placement:
    """Where the listing's runs went. Dropped runs are in neither list."""

    placed: tuple[PlacedRun, ...]
    unplaced: tuple[UnplacedRunEntry, ...]


def place_runs(
    listed: list[ListedRun],
    members_in_scope: Mapping[str, Member],
    answering_dir: Path,
    project_of: ProjectOf,
) -> Placement:
    """Place ``listed`` under ``members_in_scope`` (by project id); see the module
    docstring for the rules."""
    placed: list[PlacedRun] = []
    unplaced: list[UnplacedRunEntry] = []
    lookups: dict[Path, CFProject | CFProjectNotFound | CfCallFailed] = {}

    def refuse(run: ListedRun, reason: UnplacedReason, detail: str | None) -> None:
        if run.is_paused:
            unplaced.append(_unplaced(run, reason, detail))

    for run in listed:
        directory = run.working_directory
        if directory is None:
            refuse(run, UnplacedReason.NO_DIRECTORY, None)
        elif not directory.exists():
            refuse(run, UnplacedReason.DIRECTORY_MISSING, None)
        elif directory.resolve().is_relative_to(answering_dir.resolve()):
            continue  # an answering run's scratch: never listed, no cf call
        else:
            if directory not in lookups:
                lookups[directory] = project_of(directory)
            outcome = lookups[directory]
            if isinstance(outcome, CfCallFailed):
                refuse(run, UnplacedReason.LOOKUP_FAILED, outcome.detail)
            elif isinstance(outcome, CFProject) and outcome.id in members_in_scope:
                placed.append(PlacedRun(run, members_in_scope[outcome.id]))
    return Placement(tuple(placed), tuple(unplaced))


def _unplaced(
    run: ListedRun, reason: UnplacedReason, detail: str | None
) -> UnplacedRunEntry:
    checkpoint = run.checkpoint
    return UnplacedRunEntry(
        run_id=run.run_id,
        status=run.status,
        reason=reason,
        checkpoint_kind=None if checkpoint is None else checkpoint.kind,
        detail=detail,
    )
