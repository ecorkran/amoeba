"""``list``'s registered views: programs, members and dependencies (slice 229, D3),
and the standing answers (slice 230, D4).

Each reads the store and one ``cf list projects`` call, and fails with
``ContextForgeError`` (no partial view) when ``cf`` does not answer. A member whose
Context Forge project is gone has no name or path and is marked so; a removed member
is not listed. The models here are the JSON documents, and the CLI renders the same
objects.
"""

from __future__ import annotations

from datetime import datetime

from amoeba.config.user_config import UserConfig
from amoeba.operations.members import ContextForgeError
from amoeba.operations.set_up_models import FrozenModel
from amoeba.store.models import DependencyPair, Member, Program
from amoeba.store.programs import list_programs, members_of, pairs_of
from amoeba.store.standing import list_standing
from amoeba.store.store import Store
from amoeba.store.vocabulary import ConsumedMode, RulesFrom, StandingReach
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
    #: Context Forge name of each member and of the concept's member; null for a
    #: project Context Forge no longer lists.
    names: dict[str, str | None]


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
    #: The command a wake starts for this member, in plain text; null for none (244).
    wake_command: str | None
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


class StandingRow(FrozenModel):
    standing_id: int
    reach: StandingReach
    #: Set only for reach ``program``.
    program: str | None
    #: The member's project id; set only for reach ``member``.
    member: str | None
    #: Context Forge's name for ``member``; null for another reach, or a project
    #: Context Forge no longer lists.
    member_name: str | None
    given_at: datetime
    text: str
    #: Null for an active row; only ``all`` lists withdrawn ones.
    withdrawn_at: datetime | None
    withdraw_reason: str | None


class StandingView(FrozenModel):
    standing: tuple[StandingRow, ...]


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


def _name(details: ProjectDetails, project_id: str) -> str | None:
    known = details.get(project_id)
    return None if known is None else known.name


def programs_view(
    store: Store, run: CfRun, *, program: str | None, show_empty: bool
) -> ProgramsView:
    """Each program with its active members; empty ones only with ``show_empty``."""
    details = _details(run)

    def name_of(project_id: str) -> str | None:
        return _name(details, project_id)

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
        ids = tuple(member.project_id for member in members)
        named = (*ids, *(() if concept is None else (concept.member,)))
        rows.append(
            ProgramRow(
                program=entry.program_id,
                concept=concept,
                members=ids,
                names={project_id: name_of(project_id) for project_id in named},
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
        wake_command=settings.wake_command,
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
        return _name(details, project_id)

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


def standing_view(store: Store, run: CfRun, *, include_withdrawn: bool) -> StandingView:
    """The standing answers, newest first; withdrawn ones with ``include_withdrawn``.

    ``cf`` is read only when a member-reach row needs its member's name.
    """
    with store.read() as transaction:
        rows = list_standing(transaction, include_withdrawn=include_withdrawn)
    needs_names = any(row.member_id is not None for row in rows)
    details: ProjectDetails = _details(run) if needs_names else {}
    return StandingView(
        standing=tuple(
            StandingRow(
                standing_id=row.standing_id,
                reach=row.reach,
                program=row.program_id,
                member=row.member_id,
                member_name=None
                if row.member_id is None
                else _name(details, row.member_id),
                given_at=row.given_at,
                text=row.text,
                withdrawn_at=row.withdrawn_at,
                withdraw_reason=row.withdraw_reason,
            )
            for row in rows
        )
    )
