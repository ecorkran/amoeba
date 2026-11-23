"""``add``: register the working directory's repo, or any repo (slice 229, D4, D5).

``add`` builds a ``SetUpRequest`` and calls the ``set_up`` engine, so every guard and
every result field is the engine's. The request is either ``bulk`` (a whole
``SetUpRequest``, handed over as given) or the fields of one member; never both.

Program choice (D5): the request's ``program``; else the program the member already
belongs to (a removed member's too, so ``rm`` then ``add`` revives it where it was);
else a new program named for the member. The member for this directory's checkout is
chosen by ``add_member`` (261 D7).
"""

from __future__ import annotations

from typing import Any, Final, Self

from pydantic import ValidationError, model_validator
from pydantic.json_schema import SkipJsonSchema

from amoeba.answering.settings import RulesPath
from amoeba.config.user_config import UserConfig
from amoeba.operations.add_member import MemberPlan, plan_member
from amoeba.operations.caller import find_member
from amoeba.operations.here_document import HereNotAProject
from amoeba.operations.set_up import (
    apply_set_up,
    malformed_result,
    set_up,
    working_directory_of,
)
from amoeba.operations.set_up_models import (
    ConceptRequest,
    DependsOnRequest,
    FrozenModel,
    MemberRequest,
    NonBlankText,
    SetUpProblem,
    SetUpProblemCode,
    SetUpRequest,
    SetUpResult,
    WakeCommand,
    WorkingDirectoryNotAProject,
    rejected_result,
)
from amoeba.operations.set_up_resolve import RUN_ADD_THERE, Gathered
from amoeba.store.programs import get_member_any
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import ConsumedMode

#: No door-specific wording: each door (the CLI renderer, MCP) adds its own fix.
NOT_A_PROJECT_DETAIL: Final = "this directory is not a Context Forge project"


class AddDependsOn(FrozenModel):
    #: A member's name or id.
    provider: NonBlankText
    #: Omitted takes the config's ``default_consumed``.
    consumed: ConsumedMode | None = None


class AddRequest(FrozenModel):
    """``bulk``, or the fields of one member. Omitted differs from given."""

    bulk: SetUpRequest | None = None
    program: NonBlankText | None = None
    #: A member's name or id (261 D7); omitted means this directory's checkout.
    project: NonBlankText | None = None
    #: Sets or changes the member's name.
    name: NonBlankText | None = None
    #: Attach this checkout to the member with no checkout (D7).
    attach_to: NonBlankText | None = None
    #: Make a new member of this checkout (D7).
    new_member: bool = False
    rules_paths: tuple[RulesPath, ...] | None = None
    rules_default: bool = False
    authorize_allow: tuple[NonBlankText, ...] | None = None
    authorize_deny: tuple[NonBlankText, ...] | None = None
    depends_on: tuple[AddDependsOn, ...] = ()
    concept: ConceptRequest | None = None
    #: Omitted leaves this checkout's wake command; null clears it (244 D1). Hidden
    #: from the published schema: only the CLI door takes it.
    wake_command: SkipJsonSchema[WakeCommand | None] = None

    @model_validator(mode="after")
    def _bulk_or_single(self) -> Self:
        singles = sorted(self.model_fields_set - {"bulk"})
        if "bulk" in self.model_fields_set and self.bulk is None:
            # An empty request file parses to null: not a request, never "no flags".
            raise ValueError("bulk must be a request document, not null")
        if self.bulk is not None and singles:
            raise ValueError(f"bulk cannot be combined with {', '.join(singles)}")
        return self

    @model_validator(mode="after")
    def _one_way_to_choose_the_member(self) -> Self:
        chosen = [
            field
            for field, given in (
                ("project", self.project is not None),
                ("attach_to", self.attach_to is not None),
                ("new_member", self.new_member),
            )
            if given
        ]
        if len(chosen) > 1:
            raise ValueError(f"{' and '.join(chosen)} cannot be combined")
        return self


def single_member_request(
    request: AddRequest, config: UserConfig, program_id: str
) -> SetUpRequest:
    """The ``SetUpRequest`` for the one member; omitted fields stay omitted.

    The entry's ``project`` is the request's, or nothing for this directory's
    checkout; ``name`` rides along only for a named member (this checkout's name is
    part of its plan).
    """
    given = request.model_fields_set
    member: dict[str, Any] = {
        name: getattr(request, name)
        for name in (
            "rules_paths",
            "rules_default",
            "authorize_allow",
            "authorize_deny",
            "wake_command",
        )
        if name in given
    }
    member["depends_on"] = tuple(
        DependsOnRequest(
            provider=entry.provider,
            consumed=config.default_consumed
            if entry.consumed is None
            else entry.consumed,
        )
        for entry in request.depends_on
    )
    if request.project is not None and request.name is not None:
        member["name"] = request.name
    document: dict[str, Any] = {
        "program": program_id,
        "members": (
            MemberRequest.model_validate({"project": request.project, **member}),
        ),
    }
    if "concept" in given:
        document["concept"] = request.concept
    return SetUpRequest.model_validate(document)


def names_no_member(request: AddRequest) -> bool:
    """Whether the request has an entry that names no member, so it needs ``here``."""
    if request.bulk is not None:
        return any(entry.project is None for entry in request.bulk.members)
    return request.project is None


def add(
    store: Store, config: UserConfig, document: object, *, here: Gathered
) -> SetUpResult:
    """Apply the ``add`` request ``document``, which is validated here.

    ``here`` is what ``add_gather.gather_add`` read from the caller's directory, or
    ``None`` when the request names every member. Refusing a field the call's door may
    not set is the client part's job (``refuse_door_fields``), so this takes no door.

    Raises:
        StoreError: The store failed.
    """
    try:
        request = AddRequest.model_validate(document)
    except ValidationError as error:
        return malformed_result(error)
    if request.bulk is not None:
        return set_up(store, config, request.bulk, here=here)
    with store.write() as transaction:
        return _add_one(transaction, config, request, here)


def _add_one(
    transaction: Transaction, config: UserConfig, request: AddRequest, here: Gathered
) -> SetUpResult:
    """One member: a named one, or this directory's checkout by D7's steps."""
    plan: MemberPlan | None = None
    if request.project is not None:
        named = find_member(transaction, request.project)
        if named is None:
            problem = SetUpProblem(
                code=SetUpProblemCode.NOT_A_MEMBER,
                detail=f"project {request.project!r}: no member is named or has "
                f"that id; {RUN_ADD_THERE}",
            )
            return rejected_result([problem], working_directory_of(transaction, here))
        program = request.program or named.program_id
    else:
        planned = _plan_for(transaction, request, here)
        if isinstance(planned, SetUpResult):
            return planned
        plan = planned
        program = request.program or _program_of(transaction, plan)
    try:
        built = single_member_request(request, config, program)
    except ValidationError as error:
        # The member's own rules (rules_default with rules_paths, a key both allowed
        # and denied) are checked here, so they are `malformed` like any bad request.
        return malformed_result(error)
    return apply_set_up(transaction, config, built, here, plan)


def _plan_for(
    transaction: Transaction, request: AddRequest, here: Gathered
) -> MemberPlan | SetUpResult:
    """The plan for this directory's checkout, or the rejection that ends the call."""
    if isinstance(here, HereNotAProject):
        problem = SetUpProblem(
            code=SetUpProblemCode.NOT_A_PROJECT,
            detail=f"{NOT_A_PROJECT_DETAIL} (cf said: {here.not_a_project})",
        )
        return rejected_result(
            [problem], WorkingDirectoryNotAProject(not_a_project=here.not_a_project)
        )
    if here is None:
        problem = SetUpProblem(
            code=SetUpProblemCode.MALFORMED,
            detail="this request names no member and nothing was gathered from the "
            "working directory; run it from a checkout or name a member",
        )
        return rejected_result([problem])
    planned = plan_member(
        transaction,
        here,
        name=request.name,
        attach_to=request.attach_to,
        new_member=request.new_member,
        program=request.program,
    )
    if isinstance(planned, SetUpProblem):
        return rejected_result([planned], working_directory_of(transaction, here))
    return planned


def _program_of(transaction: Transaction, plan: MemberPlan) -> str:
    """The program the plan puts the member in: its own for an existing member."""
    if plan.program_id is not None:
        return plan.program_id
    stored = get_member_any(transaction, plan.member_id)
    if stored is None:
        raise ValueError(f"member {plan.member_id!r} is planned but not stored")
    return stored.program_id
