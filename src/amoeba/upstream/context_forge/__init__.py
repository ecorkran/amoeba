"""Context Forge's ``projects.json``: parse a project's projection, diff it."""

from amoeba.upstream.context_forge.diff import diff_states
from amoeba.upstream.context_forge.projects_file import (
    ABSENT,
    PROJECTS_FILE_NAME,
    CFFieldChange,
    CFProjectState,
    CFReadFailure,
    CFReadOutcome,
    parse,
)

__all__ = [
    "ABSENT",
    "PROJECTS_FILE_NAME",
    "CFFieldChange",
    "CFProjectState",
    "CFReadFailure",
    "CFReadOutcome",
    "diff_states",
    "parse",
]
