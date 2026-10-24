"""Hand-built plan reads for the reconcile tests."""

from __future__ import annotations

from collections.abc import Mapping

from amoeba.runner.lifecycle.plan_read import NoSlicePlan, PlanRead, SliceRead
from amoeba.upstream.context_forge import CFInitiative, CFSliceEntry, CFSliceList


def cf_initiative(
    index: int,
    *,
    name: str | None = None,
    arch_file: str | None = None,
    is_checked: bool = False,
    status: str = "in_progress",
) -> CFInitiative:
    """An initiative as ``cf list initiatives -a`` reports it."""
    return CFInitiative.model_validate(
        {
            "index": index,
            "name": name or f"Initiative {index}",
            "isChecked": is_checked,
            "archFile": arch_file,
            "status": status,
        }
    )


def cf_slice(
    index: int,
    *,
    name: str | None = None,
    design_file: str | None = None,
    is_checked: bool = False,
    status: str = "not_started",
) -> CFSliceEntry:
    """A slice as ``cf list slices`` reports it."""
    return CFSliceEntry.model_validate(
        {
            "index": index,
            "name": name or f"Slice {index}",
            "isChecked": is_checked,
            "designFile": design_file,
            "status": status,
        }
    )


def slice_list(*entries: CFSliceEntry) -> CFSliceList:
    return CFSliceList(entries=tuple(entries))


def plan(
    *initiatives: CFInitiative, slices: Mapping[int, SliceRead] | None = None
) -> PlanRead:
    """A complete read; an initiative without an entry in ``slices`` has no plan."""
    answers = dict(slices or {})
    return PlanRead(
        initiatives=tuple(initiatives),
        slices={
            initiative.index: answers.get(initiative.index, NoSlicePlan())
            for initiative in initiatives
        },
    )
