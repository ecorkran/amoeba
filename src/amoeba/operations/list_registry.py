"""``list``'s registered views: programs, members and dependencies (slice 229, D3).

Each reads the store and one ``cf list projects`` call, and fails with
``ContextForgeError`` (no partial view) when ``cf`` does not answer. A member whose
Context Forge project is gone has no name or path and is marked so; a removed member
is not listed. The models here are the JSON documents, and the CLI renders the same
objects.
"""

from __future__ import annotations

from amoeba.config.user_config import UserConfig
from amoeba.operations.members import ContextForgeError
from amoeba.operations.set_up_models import FrozenModel
from amoeba.store.models import DependencyPair, Member, Program
from amoeba.store.programs import list_programs, members_of, pairs_of
from amoeba.store.store import Store
from amoeba.store.vocabulary import ConsumedMode, RulesFrom
from amoeba.upstream.context_forge.cli_call import CfCallFailed, CfRun
from amoeba.upstream.context_forge.projects import ProjectDetails, project_details


class ConceptRow(FrozenModel):
    member: str
    path: str


class ProgramRow(FrozenModel):
    program: str
    concept: ConceptRow | None
    #: Context Forge project ids of the active members.
    members: tuple[str, ...]


class ProgramsView(FrozenModel):
    programs: tuple[ProgramRow, ...]


class DependencyRef(FrozenModel):
    provider: str
    consumed: ConsumedMode


class MemberRow(FrozenModel):
    project_id: str
    #: Null when Context Forge no longer lists the project.
    name: str | None
    #: Null when Context Forge gives the project no path, or no longer lists it.
    path: str | None
    in_context_forge: bool
    program: str
    rules_from: RulesFrom
    #: The stored entries for ``named``; the config's current ones for
    #: ``config_default``.
    rules_paths: tuple[str, ...]
    authorize_allow: tuple[str, ...]
    authorize_deny: tuple[str, ...]
    depends_on: tuple[DependencyRef, ...]


class MembersView(FrozenModel):
    members: tuple[MemberRow, ...]


class DependencyRow(FrozenModel):
    provider_id: str
    provider_name: str | None
    consumer_id: str
    consumer_name: str | None
    consumed: ConsumedMode


class DependenciesView(FrozenModel):
    dependencies: tuple[DependencyRow, ...]


def _programs(store: Store, program: str | None) -> list[Program]:
    with store.read() as transaction:
        return [
            entry
            for entry in list_programs(transaction)
            if program is None or entry.program_id == program
        ]


def _details(run: CfRun) -> ProjectDetails:
    found = project_details(run)
    if isinstance(found, CfCallFailed):
        raise ContextForgeError(found.detail)
    return found


def programs_view(
    store: Store, *, program: str | None, show_empty: bool
) -> ProgramsView:
    """Each program with its active members; empty ones only with ``show_empty``."""
    rows: list[ProgramRow] = []
    for entry in _programs(store, program):
        with store.read() as transaction:
            members = members_of(transaction, entry.program_id)
        concept = (
            None
            if entry.concept_member is None or entry.concept_path is None
            else ConceptRow(member=entry.concept_member, path=entry.concept_path)
        )
        if not members and concept is None and not show_empty:
            continue
        rows.append(
            ProgramRow(
                program=entry.program_id,
                concept=concept,
                members=tuple(member.project_id for member in members),
            )
        )
    return ProgramsView(programs=tuple(rows))


def members_view(
    store: Store, config: UserConfig, run: CfRun, *, program: str | None
) -> MembersView:
    """Each active member with its Context Forge name and path and its settings."""
    details = _details(run)
    rows: list[MemberRow] = []
    for entry in _programs(store, program):
        with store.read() as transaction:
            members = members_of(transaction, entry.program_id)
            pairs = pairs_of(transaction, entry.program_id)
        rows.extend(_member_row(member, pairs, details, config) for member in members)
    return MembersView(members=tuple(rows))


def _member_row(
    member: Member,
    pairs: tuple[DependencyPair, ...],
    details: ProjectDetails,
    config: UserConfig,
) -> MemberRow:
    settings = member.settings
    known = details.get(settings.project_id)
    default = settings.rules_from is RulesFrom.CONFIG_DEFAULT
    return MemberRow(
        project_id=settings.project_id,
        name=None if known is None else known.name,
        path=None if known is None else known.path,
        in_context_forge=known is not None,
        program=member.program_id,
        rules_from=settings.rules_from,
        rules_paths=config.default_rules_paths if default else settings.rules_paths,
        authorize_allow=settings.authorize_allow,
        authorize_deny=settings.authorize_deny,
        depends_on=tuple(
            DependencyRef(provider=pair.provider_id, consumed=pair.consumed)
            for pair in pairs
            if pair.consumer_id == settings.project_id
        ),
    )


def dependencies_view(
    store: Store, run: CfRun, *, program: str | None
) -> DependenciesView:
    """Each pair: provider to consumer, what is consumed, and both names."""
    details = _details(run)

    def name_of(project_id: str) -> str | None:
        known = details.get(project_id)
        return None if known is None else known.name

    rows: list[DependencyRow] = []
    for entry in _programs(store, program):
        with store.read() as transaction:
            pairs = pairs_of(transaction, entry.program_id)
        rows.extend(
            DependencyRow(
                provider_id=pair.provider_id,
                provider_name=name_of(pair.provider_id),
                consumer_id=pair.consumer_id,
                consumer_name=name_of(pair.consumer_id),
                consumed=pair.consumed,
            )
            for pair in pairs
        )
    return DependenciesView(dependencies=tuple(rows))
