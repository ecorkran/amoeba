"""``list``'s registered views: programs, members and dependencies (slice 229, D3),
and the standing answers (slice 230, D4).

Each reads the store and nothing else: names, ``origin`` and checkouts are stored
(slice 261, D13), so no view runs ``cf`` and none can fail on it. A member with no
checkout on the calling machine has no path and is marked so; a removed member is not
listed. The models here are the JSON documents, and the CLI renders the same objects.
"""

from __future__ import annotations

from datetime import datetime

from amoeba.config.user_config import UserConfig
from amoeba.operations.set_up_models import FrozenModel
from amoeba.store.checkouts import Checkout, checkout_listing, first_checkout_on
from amoeba.store.errors import StoreRowError
from amoeba.store.machines import acting_machine_id
from amoeba.store.models import DependencyPair, Member, Program
from amoeba.store.programs import get_member_any, list_programs, members_of, pairs_of
from amoeba.store.standing import list_standing
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import ConsumedMode, RulesFrom, StandingReach
from amoeba.store.wakes import wake_command_of


class ConceptRow(FrozenModel):
    member: str
    path: str


class ProgramRow(FrozenModel):
    program: str
    concept: ConceptRow | None
    #: The ids of the active members.
    members: tuple[str, ...]
    #: The name of each member and of the concept's member.
    names: dict[str, str]


class ProgramsView(FrozenModel):
    programs: tuple[ProgramRow, ...]


class DependencyRef(FrozenModel):
    provider: str
    consumed: ConsumedMode


class CheckoutRow(FrozenModel):
    """One checkout of a member (261 D13)."""

    machine: str
    path: str
    cf_project_id: str
    wake_command: str | None


class MemberRow(FrozenModel):
    project_id: str
    name: str
    #: The path of the member's first-added checkout on the calling machine; null when
    #: it has none there.
    path: str | None
    #: Whether the member has a checkout on the calling machine.
    in_context_forge: bool
    program: str
    rules_from: RulesFrom
    #: The stored entries for ``named``; the config's current ones for
    #: ``config_default``.
    rules_paths: tuple[str, ...]
    authorize_allow: tuple[str, ...]
    authorize_deny: tuple[str, ...]
    #: The command a wake claimed on the calling machine would run, in plain text;
    #: null for none (244, 261 D9).
    wake_command: str | None
    depends_on: tuple[DependencyRef, ...]
    #: The reduced remote that says which repo this is; null for none (261 D3).
    origin: str | None
    #: Every checkout, on every machine, the one added first first.
    checkouts: tuple[CheckoutRow, ...]


class MembersView(FrozenModel):
    members: tuple[MemberRow, ...]


class DependencyRow(FrozenModel):
    provider_id: str
    provider_name: str
    consumer_id: str
    consumer_name: str
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
    #: The name of ``member``; null for another reach.
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


def _name_in(transaction: Transaction, member_id: str) -> str:
    """The name the store holds for a member, removed members included."""
    member = get_member_any(transaction, member_id)
    if member is None:
        raise StoreRowError(f"member {member_id!r} is referenced but not stored")
    return member.name


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
            ids = tuple(member.project_id for member in members)
            named = (*ids, *(() if concept is None else (concept.member,)))
            names = {
                project_id: _name_in(transaction, project_id) for project_id in named
            }
        rows.append(
            ProgramRow(
                program=entry.program_id, concept=concept, members=ids, names=names
            )
        )
    return ProgramsView(programs=tuple(rows))


def members_view(
    store: Store, config: UserConfig, *, program: str | None
) -> MembersView:
    """Each active member with its name, origin, checkouts and settings."""
    rows: list[MemberRow] = []
    for entry in _programs(store, program):
        with store.read() as transaction:
            members = members_of(transaction, entry.program_id)
            pairs = pairs_of(transaction, entry.program_id)
            machine_id = acting_machine_id(transaction)
            for member in members:
                listing = checkout_listing(transaction, member.project_id)
                here = first_checkout_on(transaction, member.project_id, machine_id)
                rows.append(
                    _member_row(
                        member,
                        pairs,
                        config,
                        listing,
                        here,
                        wake_command_of(transaction, member.project_id),
                    )
                )
    return MembersView(members=tuple(rows))


def _member_row(  # noqa: PLR0913 - one row's inputs, all read in one transaction
    member: Member,
    pairs: tuple[DependencyPair, ...],
    config: UserConfig,
    listing: tuple[tuple[Checkout, str], ...],
    here: Checkout | None,
    wake_command: str | None,
) -> MemberRow:
    settings = member.settings
    default = settings.rules_from is RulesFrom.CONFIG_DEFAULT
    return MemberRow(
        project_id=settings.project_id,
        name=member.name,
        path=None if here is None else here.path,
        in_context_forge=here is not None,
        program=member.program_id,
        rules_from=settings.rules_from,
        rules_paths=config.default_rules_paths if default else settings.rules_paths,
        authorize_allow=settings.authorize_allow,
        authorize_deny=settings.authorize_deny,
        wake_command=wake_command,
        depends_on=tuple(
            DependencyRef(provider=pair.provider_id, consumed=pair.consumed)
            for pair in pairs
            if pair.consumer_id == settings.project_id
        ),
        origin=member.origin,
        checkouts=tuple(
            CheckoutRow(
                machine=machine,
                path=checkout.path,
                cf_project_id=checkout.cf_project_id,
                wake_command=checkout.wake_command,
            )
            for checkout, machine in listing
        ),
    )


def dependencies_view(store: Store, *, program: str | None) -> DependenciesView:
    """Each pair: provider to consumer, what is consumed, and both names."""
    rows: list[DependencyRow] = []
    for entry in _programs(store, program):
        with store.read() as transaction:
            pairs = pairs_of(transaction, entry.program_id)
            rows.extend(
                DependencyRow(
                    provider_id=pair.provider_id,
                    provider_name=_name_in(transaction, pair.provider_id),
                    consumer_id=pair.consumer_id,
                    consumer_name=_name_in(transaction, pair.consumer_id),
                    consumed=pair.consumed,
                )
                for pair in pairs
            )
    return DependenciesView(dependencies=tuple(rows))


def standing_view(store: Store, *, include_withdrawn: bool) -> StandingView:
    """The standing answers, newest first; withdrawn ones with ``include_withdrawn``."""
    with store.read() as transaction:
        rows = list_standing(transaction, include_withdrawn=include_withdrawn)
        names = {
            row.member_id: _name_in(transaction, row.member_id)
            for row in rows
            if row.member_id is not None
        }
    return StandingView(
        standing=tuple(
            StandingRow(
                standing_id=row.standing_id,
                reach=row.reach,
                program=row.program_id,
                member=row.member_id,
                member_name=None if row.member_id is None else names[row.member_id],
                given_at=row.given_at,
                text=row.text,
                withdrawn_at=row.withdrawn_at,
                withdraw_reason=row.withdraw_reason,
            )
            for row in rows
        )
    )
