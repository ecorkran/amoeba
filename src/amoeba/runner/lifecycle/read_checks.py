"""Which parts of a plan read may be applied (D5 "Safety rules").

A failed or partial read never orphans anything. :func:`checked_scope` decides, for
one link's read, whether the initiatives may be applied and which initiatives'
slice lists may be applied, and returns the ``plan_read_failed`` faults for what
was refused. It reads the tree and writes nothing.

Refused, with a fault naming the index or the count:

* a duplicate initiative index, which makes the whole read unusable;
* a repeated slice index inside one list, or one slice index listed under two
  initiatives, which removes the initiatives involved;
* an empty list while linked nodes exist (a deleted or misconfigured plan is far
  likelier than removing everything on purpose);
* a failed slice read, which removes only its initiative, and a failed initiatives
  read, which removes the link.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from amoeba.runner.faults import Fault, FaultKind
from amoeba.runner.lifecycle.plan_read import (
    PlanRead,
    PlanReadFailed,
    SliceReadFailed,
)
from amoeba.runner.lifecycle.steps import PlanObservation
from amoeba.runner.lifecycle.tree import LifecycleTree
from amoeba.store import Node, NodeKind
from amoeba.upstream.context_forge import CFSliceList


@dataclass(frozen=True)
class ReadScope:
    """What a read may be applied to.

    Attributes:
        initiatives: Whether the initiatives list may be applied.
        slice_initiatives: Indexes of the initiatives whose slice lists may be
            applied. Empty whenever ``initiatives`` is false.
        faults: One ``plan_read_failed`` fault per refusal.
    """

    initiatives: bool
    slice_initiatives: frozenset[int]
    faults: tuple[Fault, ...]


def checked_scope(
    tree: LifecycleTree, cf_project_id: str, read: PlanRead | PlanReadFailed
) -> ReadScope:
    """Apply the safety rules to one link's read."""
    if isinstance(read, PlanReadFailed):
        return _refused(f"plan read failed: {read.detail}")

    whole_link = _initiatives_problem(tree, cf_project_id, read)
    if whole_link is not None:
        return _refused(whole_link)

    faults: list[Fault] = []
    usable: dict[int, CFSliceList] = {}
    for index, got in read.slices.items():
        if isinstance(got, SliceReadFailed):
            faults.append(_fault(got.detail))
        elif isinstance(got, CFSliceList):
            usable[index] = got

    refused = _slice_list_problems(tree, cf_project_id, usable)
    faults.extend(_fault(problem) for problem in refused.values())
    in_scope = frozenset(usable) - frozenset(refused)
    return ReadScope(True, in_scope, tuple(faults))


def _fault(detail: str) -> Fault:
    return Fault(FaultKind.PLAN_READ_FAILED, detail)


def _refused(detail: str) -> ReadScope:
    return ReadScope(False, frozenset(), (_fault(detail),))


def _linked_initiatives(tree: LifecycleTree, cf_project_id: str) -> list[Node]:
    return [
        node
        for node in tree.nodes
        if node.kind is NodeKind.INITIATIVE
        and node.cf.project == cf_project_id
        and node.cf.index is not None
    ]


def _linked_slices(tree: LifecycleTree, initiative: Node | None) -> list[Node]:
    if initiative is None:
        return []
    return [
        child
        for child in tree.children(initiative)
        if child.kind is NodeKind.SLICE and child.cf.index is not None
    ]


def _initiatives_problem(
    tree: LifecycleTree, cf_project_id: str, read: PlanRead
) -> str | None:
    """Why the initiatives list cannot be applied, or ``None`` if it can."""
    indexes = [initiative.index for initiative in read.initiatives]
    repeated = sorted(i for i, count in Counter(indexes).items() if count > 1)
    if repeated:
        return f"initiative index {repeated[0]} is listed more than once"
    linked = _linked_initiatives(tree, cf_project_id)
    if not indexes and linked:
        return f"initiatives list is empty but {len(linked)} initiatives are linked"
    return None


def _slice_list_problems(
    tree: LifecycleTree, cf_project_id: str, usable: dict[int, CFSliceList]
) -> dict[int, str]:
    """Initiative index to why its slice list cannot be applied."""
    problems: dict[int, str] = {}
    owners: dict[int, list[int]] = {}
    for initiative_index, slice_list in usable.items():
        indexes = [entry.index for entry in slice_list.entries]
        for slice_index in indexes:
            owners.setdefault(slice_index, []).append(initiative_index)
        repeated = sorted(i for i, n in Counter(indexes).items() if n > 1)
        if repeated:
            problems[initiative_index] = (
                f"slice index {repeated[0]} is repeated in initiative "
                f"{initiative_index}'s list"
            )
            continue
        node = tree.find_linked(NodeKind.INITIATIVE, cf_project_id, initiative_index)
        linked = _linked_slices(tree, node)
        if not indexes and linked:
            problems[initiative_index] = (
                f"initiative {initiative_index}'s slice list is empty but "
                f"{len(linked)} slices are linked"
            )

    for slice_index, initiatives in owners.items():
        if len(initiatives) > 1:
            for initiative_index in initiatives:
                problems.setdefault(
                    initiative_index,
                    f"slice index {slice_index} is listed under initiatives "
                    f"{sorted(initiatives)}",
                )
    return problems


type ObservationKey = tuple[NodeKind, int]


def observations(
    read: PlanRead, scope: ReadScope
) -> dict[ObservationKey, PlanObservation]:
    """What the read says about each initiative and in-scope slice.

    The one place plan entries become :class:`PlanObservation` values; both the
    create and the complete rules read them.
    """
    found: dict[ObservationKey, PlanObservation] = {}
    for initiative in read.initiatives:
        found[(NodeKind.INITIATIVE, initiative.index)] = PlanObservation(
            is_checked=initiative.is_checked,
            status=initiative.status,
            arch_file=initiative.arch_file,
            slice_list_read=initiative.index in scope.slice_initiatives,
        )
    for initiative_index in scope.slice_initiatives:
        slices = read.slices[initiative_index]
        if isinstance(slices, CFSliceList):
            for entry in slices.entries:
                found[(NodeKind.SLICE, entry.index)] = PlanObservation(
                    entry.is_checked, entry.status
                )
    return found
