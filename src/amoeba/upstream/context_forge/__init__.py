"""Context Forge: ``projects.json`` (parse a project's projection, diff it) and the
plan reads (``cf list initiatives``, ``cf list slices``)."""

from amoeba.upstream.context_forge.diff import diff_states
from amoeba.upstream.context_forge.plan import (
    READ_INITIATIVES,
    READ_SLICE_LIST,
    CFErrorDocument,
    CFInitiative,
    CFSliceEntry,
    CFSliceList,
    PlanEntryLike,
    PlanEntryStatus,
    PlanParseError,
    PlanStatus,
    UnknownPlanStatus,
    parse_initiatives,
    parse_slice_list,
    reported_complete,
)
from amoeba.upstream.context_forge.projects_file import (
    ABSENT,
    PROJECTS_FILE_NAME,
    CFFieldChange,
    CFProjectState,
    CFReadFailure,
    CFReadOutcome,
    parse,
)
from amoeba.upstream.context_forge.slice_stem import SliceStem, parse_slice_stem

__all__ = [
    "ABSENT",
    "PROJECTS_FILE_NAME",
    "READ_INITIATIVES",
    "READ_SLICE_LIST",
    "CFErrorDocument",
    "CFFieldChange",
    "CFInitiative",
    "CFProjectState",
    "CFReadFailure",
    "CFReadOutcome",
    "CFSliceEntry",
    "CFSliceList",
    "PlanEntryLike",
    "PlanEntryStatus",
    "PlanParseError",
    "PlanStatus",
    "SliceStem",
    "UnknownPlanStatus",
    "diff_states",
    "parse",
    "parse_initiatives",
    "parse_slice_list",
    "parse_slice_stem",
    "reported_complete",
]
