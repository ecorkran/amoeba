"""What ``set_up`` reads and reports: the stored state of a program, the working
directory of a call, and the rejected and malformed results (slice 261, split from
``set_up`` to keep it under its size).
"""

from __future__ import annotations

from pydantic import ValidationError

from amoeba.operations.caller import NotAProject, NotInProgram, find_caller
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.set_up_models import (
    ConceptState,
    DependencyState,
    MemberState,
    ProgramState,
    SetUpOutcome,
    SetUpProblem,
    SetUpProblemCode,
    SetUpResult,
    WorkingDirectory,
    WorkingDirectoryMember,
    WorkingDirectoryNotAProject,
    WorkingDirectoryNotInProgram,
)
from amoeba.operations.set_up_resolve import Gathered
from amoeba.store.machines import acting_machine_id
from amoeba.store.models import DependencyPair, Member
from amoeba.store.programs import get_program, members_of, pairs_of
from amoeba.store.store import Transaction

#: What a validation problem names when pydantic has no field to point at.
DOCUMENT_LOCATION = "document"


def member_state(member: Member, pairs: tuple[DependencyPair, ...]) -> MemberState:
    return MemberState(
        project_id=member.project_id,
        name=member.name,
        rules_paths=member.settings.rules_paths,
        rules_from=member.settings.rules_from,
        authorize_allow=member.settings.authorize_allow,
        authorize_deny=member.settings.authorize_deny,
        depends_on=tuple(
            DependencyState(provider=pair.provider_id, consumed=pair.consumed)
            for pair in pairs
            if pair.consumer_id == member.project_id
        ),
    )


def program_state(transaction: Transaction, program_id: str) -> ProgramState | None:
    program = get_program(transaction, program_id)
    if program is None:
        return None
    pairs = pairs_of(transaction, program_id)
    concept = (
        None
        if program.concept_member is None or program.concept_path is None
        else ConceptState(member=program.concept_member, path=program.concept_path)
    )
    return ProgramState(
        program_id=program_id,
        concept=concept,
        members=tuple(
            member_state(member, pairs)
            for member in members_of(transaction, program_id)
        ),
    )


def working_directory_of(
    transaction: Transaction, here: Gathered | HereCaller
) -> WorkingDirectory | None:
    """What the call gathered about its directory; ``None`` when it gathered nothing
    (``--project``, ``rm <name>``: no ``cf`` ran, so there is no working directory)."""
    if here is None:
        return None
    if isinstance(here, HereNotAProject):
        return WorkingDirectoryNotAProject(not_a_project=here.not_a_project)
    found = find_caller(transaction, acting_machine_id(transaction), here)
    if isinstance(found, NotAProject):
        return WorkingDirectoryNotAProject(not_a_project=found.message)
    if isinstance(found, NotInProgram):
        return WorkingDirectoryNotInProgram(not_in_program=found.cf_id)
    state = member_state(found, pairs_of(transaction, found.program_id))
    return WorkingDirectoryMember(member=state, program=found.program_id)


def rejected(
    transaction: Transaction,
    program_id: str,
    here: Gathered | HereCaller,
    problems: list[SetUpProblem],
) -> SetUpResult:
    return SetUpResult(
        outcome=SetUpOutcome.REJECTED,
        change_records=(),
        problems=tuple(problems),
        program=program_state(transaction, program_id),
        working_directory=working_directory_of(transaction, here),
    )


def _location(loc: tuple[int | str, ...]) -> str:
    return ".".join(str(part) for part in loc) or DOCUMENT_LOCATION


def malformed_result(error: ValidationError) -> SetUpResult:
    """One ``malformed`` problem per pydantic error; nothing was looked up."""
    problems = tuple(
        SetUpProblem(
            code=SetUpProblemCode.MALFORMED,
            detail=f"{_location(problem['loc'])}: {problem['msg']}",
        )
        for problem in error.errors()
    )
    return SetUpResult(
        outcome=SetUpOutcome.REJECTED,
        change_records=(),
        problems=problems,
        program=None,
        working_directory=None,
    )
