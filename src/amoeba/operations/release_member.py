"""The member rule shared by ``report_release`` and ``changes`` (slice 227, D2, D3).

Both act for the member whose checkout the caller is in, found in the store from the
project id the client part gathered (261 D6). A directory that is no member is a
rejection with a detail that says which case it is, so the agent can record it.
"""

from __future__ import annotations

from amoeba.operations.caller import NotAProject, NotInProgram, find_caller
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.report_release_models import ReleaseProblem
from amoeba.store.machines import acting_machine_id
from amoeba.store.models import Member
from amoeba.store.store import Store


def not_a_member_detail(resolved: NotInProgram | NotAProject) -> str:
    """Which way a directory is no member: in no program, or in no project."""
    match resolved:
        case NotInProgram():
            return "this Context Forge project is in no program"
        case NotAProject(message=message):
            return f"this directory is in no Context Forge project: {message}"


def resolve_release_member(
    store: Store, here: HereCaller | HereNotAProject
) -> Member | ReleaseProblem:
    """The member whose checkout is ``here``, or a ``not_a_member`` problem."""
    with store.read() as transaction:
        resolved = find_caller(transaction, acting_machine_id(transaction), here)
    if isinstance(resolved, NotInProgram | NotAProject):
        return ReleaseProblem(
            code=RejectCode.NOT_A_MEMBER, detail=not_a_member_detail(resolved)
        )
    return resolved
