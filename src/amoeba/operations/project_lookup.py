"""One reading of a Context Forge project lookup for ``add`` and ``rm`` (slice 229).

A lookup that cf could not answer is a ``ContextForgeError`` (nothing is written); a
project cf does not know is a ``not_a_project`` rejection made before the engine runs,
with the text the caller gives.
"""

from __future__ import annotations

from amoeba.operations.members import ContextForgeError
from amoeba.operations.set_up_models import (
    SetUpProblem,
    SetUpProblemCode,
    SetUpResult,
    WorkingDirectoryNotAProject,
    rejected_result,
)
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.context_forge.project_of import CFProject, CFProjectNotFound


def project_or_rejection(
    found: CFProject | CFProjectNotFound | CfCallFailed, detail: str
) -> CFProject | SetUpResult:
    """The project, or the rejection that ends the call.

    Args:
        found: What ``project_of`` returned.
        detail: The rejection's detail; cf's own message follows it in parentheses.

    Raises:
        ContextForgeError: ``cf`` failed to give a usable answer.
    """
    if isinstance(found, CfCallFailed):
        raise ContextForgeError(found.detail)
    if isinstance(found, CFProject):
        return found
    problem = SetUpProblem(
        code=SetUpProblemCode.NOT_A_PROJECT,
        detail=f"{detail} (cf said: {found.message})",
    )
    return rejected_result(
        [problem], WorkingDirectoryNotAProject(not_a_project=found.message)
    )
