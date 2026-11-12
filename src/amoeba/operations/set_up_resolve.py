"""``set_up`` step 2: every project reference becomes a Context Forge id (D7).

All ``cf`` calls happen here, before the store is written, so no subprocess runs
under the write lock and a ``ContextForgeError`` stops the call with nothing written.
A reference that is no project is a ``not_a_project`` problem, not an error.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from amoeba.operations.members import ContextForgeError
from amoeba.operations.set_up_models import (
    SetUpProblem,
    SetUpProblemCode,
    SetUpRequest,
)
from amoeba.operations.set_up_remove_resolve import (
    RequestedPair,
    ResolvedRemoval,
    resolve_removal,
)
from amoeba.store.vocabulary import ConsumedMode
from amoeba.upstream.context_forge.cli_call import CfCallFailed, CfRun
from amoeba.upstream.context_forge.project_of import (
    CFProject,
    CFProjectNotFound,
    project_of,
)


@dataclass(frozen=True)
class ResolvedDependency:
    provider_ref: str
    provider_id: str
    consumed: ConsumedMode


@dataclass(frozen=True)
class ResolvedMember:
    #: Position in the request's ``members``, for problem details.
    index: int
    project_id: str
    #: ``None`` means omitted: leave the stored value.
    rules_paths: tuple[str, ...] | None
    authorize_allow: tuple[str, ...] | None
    authorize_deny: tuple[str, ...] | None
    depends_on: tuple[ResolvedDependency, ...]


@dataclass(frozen=True)
class ResolvedConcept:
    member_ref: str
    member_id: str
    path: str


@dataclass(frozen=True)
class ResolvedRequest:
    program_id: str
    #: ``False``: the request did not mention the concept; leave it.
    concept_given: bool
    #: With ``concept_given``: ``None`` clears the concept.
    concept: ResolvedConcept | None
    members: tuple[ResolvedMember, ...]
    #: What ``remove`` takes out, as ids (228 D8).
    removal: ResolvedRemoval


@dataclass(frozen=True)
class Resolution:
    #: The working directory's project, or why it has none.
    working_directory: CFProject | CFProjectNotFound
    #: ``None`` when any problem was found.
    request: ResolvedRequest | None
    problems: tuple[SetUpProblem, ...]


class _Lookups:
    """Context Forge lookups for one call, each reference asked once."""

    def __init__(self, run: CfRun) -> None:
        self._run = run
        self._by_reference: dict[str, CFProject | CFProjectNotFound] = {}

    def reference(self, reference: str) -> CFProject | CFProjectNotFound:
        if reference not in self._by_reference:
            self._by_reference[reference] = _checked(
                project_of(reference=reference, run=self._run)
            )
        return self._by_reference[reference]


def _checked(
    result: CFProject | CFProjectNotFound | CfCallFailed,
) -> CFProject | CFProjectNotFound:
    if isinstance(result, CfCallFailed):
        raise ContextForgeError(result.detail)
    return result


def _not_a_project(field: str, found: CFProjectNotFound) -> SetUpProblem:
    return SetUpProblem(
        code=SetUpProblemCode.NOT_A_PROJECT, detail=f"{field}: {found.message}"
    )


def resolve_request(request: SetUpRequest, directory: Path, run: CfRun) -> Resolution:
    """Resolve the working directory and every reference in ``request``.

    Raises:
        ContextForgeError: ``cf`` failed to give a usable answer.
    """
    working = _checked(project_of(directory=directory, run=run))
    lookups = _Lookups(run)
    problems: list[SetUpProblem] = []

    concept: ResolvedConcept | None = None
    if request.concept is not None:
        found = lookups.reference(request.concept.member)
        if isinstance(found, CFProjectNotFound):
            problems.append(_not_a_project("concept.member", found))
        else:
            concept = ResolvedConcept(
                request.concept.member, found.id, request.concept.path
            )

    members: list[ResolvedMember] = []
    first_seen: dict[str, int] = {}
    for index, entry in enumerate(request.members):
        own = f"members.{index}"
        if entry.project is None:
            project: CFProject | CFProjectNotFound = working
            where = f"{own}.project (the working directory)"
        else:
            project = lookups.reference(entry.project)
            where = f"{own}.project"
        if isinstance(project, CFProjectNotFound):
            problems.append(_not_a_project(where, project))
            continue
        if project.id in first_seen:
            problems.append(
                SetUpProblem(
                    code=SetUpProblemCode.MALFORMED,
                    detail=f"{own}.project: {project.id} is already listed as "
                    f"members.{first_seen[project.id]}",
                )
            )
            continue
        first_seen[project.id] = index
        dependencies: list[ResolvedDependency] = []
        for position, dependency in enumerate(entry.depends_on):
            provider = lookups.reference(dependency.provider)
            if isinstance(provider, CFProjectNotFound):
                problems.append(
                    _not_a_project(f"{own}.depends_on.{position}.provider", provider)
                )
                continue
            dependencies.append(
                ResolvedDependency(
                    dependency.provider, provider.id, dependency.consumed
                )
            )
        members.append(
            ResolvedMember(
                index=index,
                project_id=project.id,
                rules_paths=entry.rules_paths,
                authorize_allow=entry.authorize_allow,
                authorize_deny=entry.authorize_deny,
                depends_on=tuple(dependencies),
            )
        )

    requested_pairs = [
        RequestedPair(member.index, position, dependency.provider_id, member.project_id)
        for member in members
        for position, dependency in enumerate(member.depends_on)
    ]
    removal, removal_problems = resolve_removal(
        request.remove, lookups.reference, first_seen, requested_pairs
    )
    problems += removal_problems
    if problems:
        return Resolution(working, None, tuple(problems))
    resolved = ResolvedRequest(
        program_id=request.program,
        concept_given="concept" in request.model_fields_set,
        concept=concept,
        members=tuple(members),
        removal=removal,
    )
    return Resolution(working, resolved, ())
