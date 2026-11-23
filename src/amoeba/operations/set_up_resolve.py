"""``set_up`` step 2: every reference becomes a member (slice 261, D6, D7).

References are names or ids, found in the store inside the engine's transaction: no
``cf`` call happens here. A reference nobody matches is a ``not_a_member`` problem.
The one entry that names no member is the gathered checkout's: it follows
``add_member.plan_member`` (D7).
"""

from __future__ import annotations

from dataclasses import dataclass

from amoeba.operations.add_member import MemberPlan, plan_member
from amoeba.operations.add_names import NAME_RULE, check_given_name
from amoeba.operations.caller import find_member, find_member_for_removal
from amoeba.operations.here_document import HereCheckout, HereNotAProject
from amoeba.operations.set_up_models import (
    DependsOnRequest,
    SetUpProblem,
    SetUpProblemCode,
    SetUpRequest,
)
from amoeba.operations.set_up_remove_resolve import (
    RequestedPair,
    ResolvedRemoval,
    resolve_removal,
)
from amoeba.store.models import Member
from amoeba.store.store import Transaction
from amoeba.store.vocabulary import ConsumedMode, is_member_name

#: What the engine knows of the caller's directory: the gathered checkout, a directory
#: in no project, or nothing (a call that names every member gathers nothing).
type Gathered = HereCheckout | HereNotAProject | None

#: Said when an entry names a member that does not exist.
RUN_ADD_THERE = "run `amoeba add` in that repo to register it"
#: Said when a wake command is given for an entry that is not the caller's checkout.
WAKE_FROM_OWN_CHECKOUT = (
    "a wake command is set from its own checkout: run `amoeba add --wake-command` "
    "in that repo"
)
#: A bulk file or ``add`` may have only one entry that names no member.
ONE_UNNAMED_ENTRY = "only one entry may name no member: it is this directory's checkout"


@dataclass(frozen=True)
class ResolvedDependency:
    provider_ref: str
    provider_id: str
    provider_name: str
    consumed: ConsumedMode


@dataclass(frozen=True)
class ResolvedMember:
    #: Position in the request's ``members``, for problem details.
    index: int
    project_id: str
    name: str
    #: For the entry that names no member: what ``add_member`` decided.
    plan: MemberPlan | None
    #: For an entry that names a member and sets its name (``name``).
    rename_to: str | None
    #: ``None`` means omitted: leave the stored value.
    rules_paths: tuple[str, ...] | None
    #: Return the member to the config's default rules.
    rules_default: bool
    authorize_allow: tuple[str, ...] | None
    authorize_deny: tuple[str, ...] | None
    #: ``False``: the request did not mention the wake command; leave it.
    wake_command_given: bool
    #: With ``wake_command_given``: ``None`` clears it.
    wake_command: str | None
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
    #: ``None`` when any problem was found.
    request: ResolvedRequest | None
    problems: tuple[SetUpProblem, ...]


def _not_a_member(field: str, reference: str) -> SetUpProblem:
    return SetUpProblem(
        code=SetUpProblemCode.NOT_A_MEMBER,
        detail=f"{field}: no member is named or has the id {reference!r}; "
        f"{RUN_ADD_THERE}",
    )


def _malformed(detail: str) -> SetUpProblem:
    return SetUpProblem(code=SetUpProblemCode.MALFORMED, detail=detail)


class _Resolver:
    """The reads of one call: each reference found once, in one transaction."""

    def __init__(self, transaction: Transaction) -> None:
        self._transaction = transaction
        self._found: dict[str, Member | None] = {}

    def member(self, reference: str) -> Member | None:
        if reference not in self._found:
            self._found[reference] = find_member(self._transaction, reference)
        return self._found[reference]

    def for_removal(self, reference: str) -> Member | None:
        return find_member_for_removal(self._transaction, reference)


def resolve_request(  # noqa: PLR0913 - the request and what the call gathered
    transaction: Transaction,
    request: SetUpRequest,
    here: Gathered,
    working_plan: MemberPlan | SetUpProblem | None = None,
) -> Resolution:
    """Every reference in ``request`` as a member, and the working entry's plan.

    ``working_plan`` is the plan the caller already made for the entry that names no
    member (``add`` plans first to choose the program); with none, it is planned here.
    """
    resolver = _Resolver(transaction)
    problems: list[SetUpProblem] = []
    concept = _concept(request, resolver, problems)
    members: list[ResolvedMember] = []
    first_seen: dict[str, int] = {}
    #: Each name a member takes in this request (lower case) and the entry giving it,
    #: so two entries cannot take one name, which the store's unique index would refuse.
    claimed: dict[str, int] = {}
    unnamed: int | None = None
    for index, entry in enumerate(request.members):
        own = f"members.{index}"
        plan: MemberPlan | None = None
        rename_to: str | None = None
        if entry.project is None:
            if unnamed is not None:
                problems.append(_malformed(f"{own}.project: {ONE_UNNAMED_ENTRY}"))
                continue
            unnamed = index
            resolved = _working_entry(
                transaction, entry.name, here, working_plan, request.program, own
            )
            if isinstance(resolved, SetUpProblem):
                problems.append(resolved)
                continue
            plan = resolved
            project_id, name = plan.member_id, plan.name
        else:
            stored = resolver.member(entry.project)
            if stored is None:
                problems.append(_not_a_member(f"{own}.project", entry.project))
                continue
            project_id, name = stored.project_id, stored.name
            if entry.name is not None:
                refused = _rename(transaction, entry.name, project_id, own)
                if refused is not None:
                    problems.append(refused)
                    continue
                rename_to = entry.name
            if "wake_command" in entry.model_fields_set:
                problems.append(
                    _malformed(f"{own}.wake_command: {WAKE_FROM_OWN_CHECKOUT}")
                )
                continue
        if project_id in first_seen:
            problems.append(
                _malformed(
                    f"{own}.project: {name} is already listed as "
                    f"members.{first_seen[project_id]}"
                )
            )
            continue
        claimed_name = _name_given(rename_to, plan)
        if claimed_name is not None:
            other = claimed.get(claimed_name.lower())
            if other is not None:
                problems.append(
                    SetUpProblem(
                        code=SetUpProblemCode.NAME_TAKEN,
                        detail=f"{own}.name: {claimed_name!r} is also given to "
                        f"members.{other} in this request; a name is one member's",
                    )
                )
                continue
            claimed[claimed_name.lower()] = index
        first_seen[project_id] = index
        dependencies = _dependencies(entry.depends_on, own, resolver, problems)
        members.append(
            ResolvedMember(
                index=index,
                project_id=project_id,
                name=name,
                plan=plan,
                rename_to=rename_to,
                rules_paths=entry.rules_paths,
                rules_default=entry.rules_default,
                authorize_allow=entry.authorize_allow,
                authorize_deny=entry.authorize_deny,
                wake_command_given="wake_command" in entry.model_fields_set,
                wake_command=entry.wake_command,
                depends_on=tuple(dependencies),
            )
        )
    requested_pairs = [
        RequestedPair(member.index, position, dependency.provider_id, member.project_id)
        for member in members
        for position, dependency in enumerate(member.depends_on)
    ]
    removal, removal_problems = resolve_removal(
        request.remove, resolver.for_removal, first_seen, requested_pairs
    )
    problems += removal_problems
    if problems:
        return Resolution(None, tuple(problems))
    return Resolution(
        ResolvedRequest(
            program_id=request.program,
            concept_given="concept" in request.model_fields_set,
            concept=concept,
            members=tuple(members),
            removal=removal,
        ),
        (),
    )


def _concept(
    request: SetUpRequest, resolver: _Resolver, problems: list[SetUpProblem]
) -> ResolvedConcept | None:
    if request.concept is None:
        return None
    found = resolver.member(request.concept.member)
    if found is None:
        problems.append(_not_a_member("concept.member", request.concept.member))
        return None
    return ResolvedConcept(
        request.concept.member, found.project_id, request.concept.path
    )


def _dependencies(
    entries: tuple[DependsOnRequest, ...],
    own: str,
    resolver: _Resolver,
    problems: list[SetUpProblem],
) -> list[ResolvedDependency]:
    resolved: list[ResolvedDependency] = []
    for position, dependency in enumerate(entries):
        provider = resolver.member(dependency.provider)
        if provider is None:
            problems.append(
                _not_a_member(
                    f"{own}.depends_on.{position}.provider", dependency.provider
                )
            )
            continue
        resolved.append(
            ResolvedDependency(
                dependency.provider,
                provider.project_id,
                provider.name,
                dependency.consumed,
            )
        )
    return resolved


def _name_given(rename_to: str | None, plan: MemberPlan | None) -> str | None:
    """The name an entry gives a member in this call, or ``None`` when it gives none."""
    if rename_to is not None:
        return rename_to
    if plan is not None and (plan.is_new or plan.renamed_from is not None):
        return plan.name
    return None


def _rename(
    transaction: Transaction, name: str, member_id: str, own: str
) -> SetUpProblem | None:
    """A member named by an entry takes ``name``, when it is a valid free name."""
    if not is_member_name(name):
        return _malformed(f"{own}.name: {name!r} is not a member name: {NAME_RULE}")
    refused = check_given_name(transaction, name, member_id)
    if refused is None:
        return None
    return SetUpProblem(code=refused.code, detail=f"{own}.name: {refused.detail}")


def _working_entry(  # noqa: PLR0913 - the entry's inputs and the call's gathered value
    transaction: Transaction,
    name: str | None,
    here: Gathered,
    working_plan: MemberPlan | SetUpProblem | None,
    program: str,
    own: str,
) -> MemberPlan | SetUpProblem:
    """The plan for the entry that names no member: this directory's checkout."""
    if isinstance(here, HereNotAProject):
        return SetUpProblem(
            code=SetUpProblemCode.NOT_A_PROJECT,
            detail=f"{own}.project (the working directory): {here.not_a_project}",
        )
    if here is None:
        return _malformed(
            f"{own}.project: the entry names no member and nothing was gathered "
            "from the working directory; name a member or run it from a checkout"
        )
    if working_plan is not None:
        return working_plan
    return plan_member(
        transaction,
        here,
        name=name,
        attach_to=None,
        new_member=False,
        program=program,
    )
