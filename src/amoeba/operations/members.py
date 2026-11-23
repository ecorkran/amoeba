"""Which program member a directory is (slice 222, D6).

A directory resolves to its Context Forge project, then to that project's membership.
Worktrees and subdirectories of one repo are one member because Context Forge gives
them one project id; Amoeba adds no worktree logic. The ``cf`` call is made before
the store is touched, so no subprocess runs under a lock.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.operations.caller import NotAProject, NotInProgram
from amoeba.operations.errors import ContextForgeError
from amoeba.store.models import Member
from amoeba.store.programs import get_member
from amoeba.store.store import Store
from amoeba.upstream.context_forge.cli_call import CfCallFailed, CfRun
from amoeba.upstream.context_forge.project_of import (
    CFProjectNotFound,
    project_of,
)


def resolve_member(
    store: Store, directory: Path, run: CfRun
) -> Member | NotInProgram | NotAProject:
    """The member whose repo contains ``directory``.

    Raises:
        ContextForgeError: ``cf`` failed to give a usable answer.
    """
    project = project_of(directory=directory, run=run)
    if isinstance(project, CfCallFailed):
        raise ContextForgeError(project.detail)
    if isinstance(project, CFProjectNotFound):
        return NotAProject(project.message)
    with store.read() as transaction:
        member = get_member(transaction, project.id)
    return NotInProgram(project.id) if member is None else member
