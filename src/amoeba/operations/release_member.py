"""The member rule shared by ``report_release`` and ``changes`` (slice 227, D2, D3).

Both act for the member whose checkout the caller is in. A directory that is no
member is a rejection with a detail that says which case it is, so the agent can
record it; a ``cf`` failure is not a rejection and propagates.
"""

from __future__ import annotations

from pathlib import Path

from amoeba.operations.members import (
    NotAProject,
    NotInProgram,
    resolve_member,
)
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.report_release_models import ReleaseProblem
from amoeba.store.models import Member
from amoeba.store.store import Store
from amoeba.upstream.context_forge.cli_call import CfRun


def not_a_member_detail(resolved: NotInProgram | NotAProject) -> str:
    """Which way a directory is no member: in no program, or in no project."""
    match resolved:
        case NotInProgram():
            return "this Context Forge project is in no program"
        case NotAProject(message=message):
            return f"this directory is in no Context Forge project: {message}"


def resolve_release_member(
    store: Store, directory: Path, cf_run: CfRun
) -> Member | ReleaseProblem:
    """The member ``directory`` belongs to, or a ``not_a_member`` problem.

    Raises:
        ContextForgeError: ``cf`` failed to give a usable answer.
    """
    resolved = resolve_member(store, directory, cf_run)
    if isinstance(resolved, NotInProgram | NotAProject):
        return ReleaseProblem(
            code=RejectCode.NOT_A_MEMBER, detail=not_a_member_detail(resolved)
        )
    return resolved
