"""``set_up``: register or update a program, its members and dependency pairs (D7).

The flow: validate the document, then in one write transaction find every reference
in the store (no ``cf`` runs: the client part gathered what it needed, 261 D5), read
the stored state, run the checks, and either write or return the problems. What the
request names under ``members`` is created or set, and a given list replaces the
stored value whole; only what it names under ``remove`` is removed (228 D8). A repeat
writes nothing and returns ``unchanged``.

The request and result models live in ``set_up_models``; they are importable from
here too.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError

from amoeba.config.user_config import UserConfig
from amoeba.operations.add_member import MemberPlan
from amoeba.operations.here_document import HereCaller, HereCheckout
from amoeba.operations.set_up_checks import check_request
from amoeba.operations.set_up_models import (
    Change,
    ChangeSubject,
    ChangeVerb,
    SetUpOutcome,
    SetUpProblem,
    SetUpProblemCode,
    SetUpRequest,
    SetUpResult,
)
from amoeba.operations.set_up_plan import apply_plan, name_before_write
from amoeba.operations.set_up_remove import apply_removal
from amoeba.operations.set_up_resolve import (
    Gathered,
    ResolvedMember,
    ResolvedRequest,
    resolve_request,
)
from amoeba.operations.set_up_state import (
    malformed_result,
    program_state,
    rejected,
    working_directory_of,
)
from amoeba.operations.set_up_wake import apply_wake_commands
from amoeba.store.member_names import set_member_name
from amoeba.store.models import MemberSettings
from amoeba.store.programs import (
    get_member,
    get_pair,
    get_program,
    upsert_member,
    upsert_pair,
    upsert_program,
)
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import RulesFrom

__all__ = [
    "SetUpProblemCode",
    "SetUpRequest",
    "SetUpResult",
    "set_up",
]

# --- writes ------------------------------------------------------------------


def _merged_rules(
    member: ResolvedMember, stored: MemberSettings | None
) -> tuple[tuple[str, ...], RulesFrom]:
    """The member's rules after the request (229 D7).

    Given ``rules_paths`` (even ``[]``) are named; ``rules_default``, or a new member
    with neither, is the config default and stores no list; otherwise the stored
    choice stays.
    """
    if member.rules_paths is not None:
        return member.rules_paths, RulesFrom.NAMED
    if member.rules_default or stored is None:
        return (), RulesFrom.CONFIG_DEFAULT
    return stored.rules_paths, stored.rules_from


def _merged_settings(
    member: ResolvedMember, stored: MemberSettings | None
) -> MemberSettings:
    """The member's settings after the request: a given list replaces, else stays."""

    def pick(
        given: tuple[str, ...] | None, kept: tuple[str, ...] | None
    ) -> tuple[str, ...]:
        if given is not None:
            return given
        return () if kept is None else kept

    rules_paths, rules_from = _merged_rules(member, stored)
    return MemberSettings(
        project_id=member.project_id,
        rules_paths=rules_paths,
        authorize_allow=pick(member.authorize_allow, stored and stored.authorize_allow),
        authorize_deny=pick(member.authorize_deny, stored and stored.authorize_deny),
        rules_from=rules_from,
    )


def _write_concept(
    transaction: Transaction, request: ResolvedRequest, now: datetime
) -> list[Change]:
    stored = get_program(transaction, request.program_id)
    if request.concept_given:
        member = None if request.concept is None else request.concept.member_id
        path = None if request.concept is None else request.concept.path
    else:
        member = None if stored is None else stored.concept_member
        path = None if stored is None else stored.concept_path
    changed = upsert_program(
        transaction,
        program_id=request.program_id,
        concept_member=member,
        concept_path=path,
        now=now,
    )
    if not changed:
        return []
    verb = ChangeVerb.ADDED if stored is None else ChangeVerb.UPDATED
    return [Change(verb=verb, subject=ChangeSubject.PROGRAM, detail=request.program_id)]


def _write_member(
    transaction: Transaction,
    request: ResolvedRequest,
    member: ResolvedMember,
    here: Gathered | HereCaller,
    now: datetime,
) -> list[Change]:
    stored = get_member(transaction, member.project_id)
    plan = member.plan
    if plan is not None:
        name_before_write(transaction, plan, now)
    program_id = request.program_id
    changed = upsert_member(
        transaction,
        program_id=program_id,
        settings=_merged_settings(member, None if stored is None else stored.settings),
        name=member.name,
        now=now,
    )
    changes: list[Change] = []
    if changed:
        verb = ChangeVerb.ADDED if stored is None else ChangeVerb.UPDATED
        changes.append(
            Change(verb=verb, subject=ChangeSubject.MEMBER, detail=member.name)
        )
    if plan is not None and isinstance(here, HereCheckout):
        changes += apply_plan(transaction, plan, here, now)
    if member.rename_to is not None and member.rename_to != member.name:
        set_member_name(transaction, member.project_id, member.rename_to, now)
        changes.append(
            Change(
                verb=ChangeVerb.UPDATED,
                subject=ChangeSubject.MEMBER,
                detail=f"{member.name} is now named {member.rename_to}",
            )
        )
    return changes


def _write_pairs(
    transaction: Transaction,
    request: ResolvedRequest,
    member: ResolvedMember,
    now: datetime,
) -> list[Change]:
    changes: list[Change] = []
    for dependency in member.depends_on:
        stored = get_pair(transaction, dependency.provider_id, member.project_id)
        changed = upsert_pair(
            transaction,
            program_id=request.program_id,
            provider_id=dependency.provider_id,
            consumer_id=member.project_id,
            consumed=dependency.consumed,
            now=now,
        )
        if changed:
            verb = ChangeVerb.ADDED if stored is None else ChangeVerb.UPDATED
            changes.append(
                Change(
                    verb=verb,
                    subject=ChangeSubject.DEPENDENCY,
                    detail=f"{member.name} on {dependency.provider_name} "
                    f"({dependency.consumed.value})",
                )
            )
    return changes


def _apply(
    transaction: Transaction,
    request: ResolvedRequest,
    here: Gathered | HereCaller,
) -> SetUpResult:
    now = datetime.now(UTC)
    changes = _write_concept(transaction, request, now)
    for member in request.members:
        changes += _write_member(transaction, request, member, here, now)
    changes += apply_wake_commands(transaction, request.members, here, now, changes)
    # Pairs after every member exists: a provider may be added in this request.
    for member in request.members:
        changes += _write_pairs(transaction, request, member, now)
    changes += apply_removal(transaction, request.removal, now)
    return SetUpResult(
        outcome=SetUpOutcome.APPLIED if changes else SetUpOutcome.UNCHANGED,
        change_records=tuple(changes),
        problems=(),
        program=program_state(transaction, request.program_id),
        working_directory=working_directory_of(transaction, here),
    )


def apply_set_up(  # noqa: PLR0913 - the transaction, the request and what was gathered
    transaction: Transaction,
    config: UserConfig,
    request: SetUpRequest,
    here: Gathered | HereCaller,
    working_plan: MemberPlan | SetUpProblem | None = None,
) -> SetUpResult:
    """The engine inside the caller's write transaction: find the references, run the
    checks, and either write or return the problems. Nothing is written when a
    problem is found, so the transaction may commit as it is."""
    resolution = resolve_request(
        transaction,
        request,
        here if not isinstance(here, HereCaller) else None,
        working_plan,
    )
    problems = list(resolution.problems)
    if resolution.request is not None:
        problems += check_request(transaction, config, resolution.request)
    if problems or resolution.request is None:
        return rejected(transaction, request.program, here, problems)
    return _apply(transaction, resolution.request, here)


def set_up(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    here: Gathered | HereCaller,
) -> SetUpResult:
    """Apply the ``set_up`` request ``document``, which is validated here.

    ``here`` is what the client part gathered from the caller's directory, or
    ``None`` when the request names every member.

    Raises:
        StoreError: The store failed.
    """
    try:
        request = SetUpRequest.model_validate(document)
    except ValidationError as error:
        return malformed_result(error)
    with store.write() as transaction:
        return apply_set_up(transaction, config, request, here)
