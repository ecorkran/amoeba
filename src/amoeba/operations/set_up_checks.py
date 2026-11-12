"""``set_up`` step 3: the checks, run against the state the request would produce (D7).

Called inside the write transaction, so what is read is what would be written to.
Every problem is collected; any one rejects the whole request.
"""

from __future__ import annotations

from amoeba.config.user_config import UserConfig
from amoeba.operations.set_up_models import SetUpProblem, SetUpProblemCode
from amoeba.operations.set_up_remove import check_removal
from amoeba.operations.set_up_resolve import ResolvedMember, ResolvedRequest
from amoeba.store.programs import get_member, get_program, members_of
from amoeba.store.store import Transaction


def _problem(code: SetUpProblemCode, detail: str) -> SetUpProblem:
    return SetUpProblem(code=code, detail=detail)


def _member_problems(
    transaction: Transaction,
    config_keys: frozenset[str],
    program_id: str,
    member: ResolvedMember,
    members_after: frozenset[str],
) -> list[SetUpProblem]:
    own = f"members.{member.index}"
    problems: list[SetUpProblem] = []
    stored = get_member(transaction, member.project_id)
    if stored is None and member.rules_paths is None:
        problems.append(
            _problem(
                SetUpProblemCode.RULES_PATHS_REQUIRED,
                f"{own}: {member.project_id} is new and needs rules_paths",
            )
        )
    for field, keys in (
        ("authorize_allow", member.authorize_allow),
        ("authorize_deny", member.authorize_deny),
    ):
        problems.extend(
            _problem(
                SetUpProblemCode.UNKNOWN_AUTHORIZE_ITEM,
                f"{own}.{field}: {key!r} is not in the config's authorize_items",
            )
            for key in keys or ()
            if key not in config_keys
        )
    for position, dependency in enumerate(member.depends_on):
        field = f"{own}.depends_on.{position}.provider"
        if dependency.provider_id == member.project_id:
            problems.append(
                _problem(
                    SetUpProblemCode.SELF_DEPENDENCY,
                    f"{field}: {member.project_id} cannot depend on itself",
                )
            )
        elif dependency.provider_id not in members_after:
            problems.append(
                _problem(
                    SetUpProblemCode.UNKNOWN_PROVIDER,
                    f"{field}: {dependency.provider_ref!r} "
                    f"({dependency.provider_id}) is not a member of program "
                    f"{program_id!r}",
                )
            )
    return problems


def check_request(
    transaction: Transaction, config: UserConfig, request: ResolvedRequest
) -> list[SetUpProblem]:
    """Every problem the request has against the stored state and the config."""
    program_id = request.program_id
    problems: list[SetUpProblem] = []
    if get_program(transaction, program_id) is None and not request.members:
        problems.append(
            _problem(
                SetUpProblemCode.EMPTY_PROGRAM,
                f"program {program_id!r} does not exist and the request adds no member",
            )
        )
    members_after = {
        member.project_id for member in members_of(transaction, program_id)
    } - request.removal.member_ids
    for member in request.members:
        stored = get_member(transaction, member.project_id)
        if stored is not None and stored.program_id != program_id:
            problems.append(
                _problem(
                    SetUpProblemCode.MEMBER_OF_OTHER_PROGRAM,
                    f"members.{member.index}: {member.project_id} already belongs "
                    f"to program {stored.program_id!r}",
                )
            )
        else:
            members_after.add(member.project_id)
    config_keys = frozenset(item.key for item in config.authorize_items)
    for member in request.members:
        problems.extend(
            _member_problems(
                transaction, config_keys, program_id, member, frozenset(members_after)
            )
        )
    problems.extend(
        check_removal(
            transaction,
            program_id,
            request.removal,
            concept_given=request.concept_given,
        )
    )
    concept = request.concept
    if concept is not None and concept.member_id not in members_after:
        problems.append(
            _problem(
                SetUpProblemCode.CONCEPT_MEMBER_NOT_MEMBER,
                f"concept.member: {concept.member_ref!r} ({concept.member_id}) "
                f"is not a member of program {program_id!r}",
            )
        )
    return problems
