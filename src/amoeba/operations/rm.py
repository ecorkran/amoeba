"""``rm``: remove members, pairs, the concept or one checkout (slice 229, D6; 261, D8).

``rm`` finds the program from the store, builds the ``remove`` section of a
``SetUpRequest`` and calls the ``set_up`` engine, so soft removal, open-question
refusals and ``not_a_member`` are the engine's. A member is named by name or id and
found in the store, so ``rm <name>`` gathers nothing and works from any machine and
directory. With nothing named it removes the caller's member, found by the gathered
checkout. ``rm --checkout PATH`` removes one checkout of this machine and leaves the
member.
"""

from __future__ import annotations

from typing import Any, Final

from pydantic import ValidationError, field_validator

from amoeba.config.user_config import UserConfig
from amoeba.operations.caller import (
    NotAProject,
    NotInProgram,
    find_caller,
    find_member_for_removal,
)
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.set_up import malformed_result, set_up
from amoeba.operations.set_up_models import (
    Change,
    ChangeSubject,
    ChangeVerb,
    FrozenModel,
    NonBlankText,
    SetUpOutcome,
    SetUpProblem,
    SetUpProblemCode,
    SetUpResult,
    rejected_result,
)
from amoeba.store.checkouts import checkouts_on_machine, delete_checkouts_at_path
from amoeba.store.machines import acting_machine_id
from amoeba.store.programs import get_program
from amoeba.store.store import Store, Transaction

PAIR_SEPARATOR: Final = ":"
#: No door-specific wording: each door (the CLI renderer, MCP) adds its own fix.
NOT_A_PROJECT_DETAIL: Final = (
    "this directory is not a Context Forge project and no member was named"
)


class RmRequest(FrozenModel):
    #: Members' names or ids. None named (and no pair, no concept) means the caller's
    #: member.
    members: tuple[NonBlankText, ...] = ()
    #: ``PROVIDER:CONSUMER``, each a member's name or id.
    pairs: tuple[NonBlankText, ...] = ()
    #: Clear the program's concept, the only way to remove the concept's member.
    concept: bool = False
    #: The program, when it cannot be told from the members.
    program: NonBlankText | None = None
    #: Remove the checkout of this machine stored at this absolute path (D8).
    checkout: NonBlankText | None = None

    @field_validator("pairs")
    @classmethod
    def _each_pair_has_two_ends(cls, pairs: tuple[str, ...]) -> tuple[str, ...]:
        for pair in pairs:
            provider, separator, consumer = pair.partition(PAIR_SEPARATOR)
            if not (separator and provider.strip() and consumer.strip()):
                raise ValueError(f"{pair!r} must be PROVIDER{PAIR_SEPARATOR}CONSUMER")
        return pairs


def split_pair(pair: str) -> tuple[str, str]:
    provider, _, consumer = pair.partition(PAIR_SEPARATOR)
    return provider.strip(), consumer.strip()


def needs_here(document: object) -> bool:
    """Whether the gathered caller is needed (D5): nothing says which program or
    checkout is meant. A document that does not parse needs nothing; ``rm`` rejects it.
    """
    try:
        request = RmRequest.model_validate(document)
    except ValidationError:
        # Not a valid request: rm returns the malformed rejection, no caller.
        return False
    if request.checkout is not None or request.members or request.pairs:
        return False
    return not (request.concept and request.program is not None)


def rm(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    here: HereCaller | HereNotAProject | None,
) -> SetUpResult:
    """Apply the ``rm`` request ``document``, which is validated here.

    ``here`` is what the client part gathered, only when ``needs_here`` said so.

    Raises:
        StoreError: The store failed.
    """
    try:
        request = RmRequest.model_validate(document)
    except ValidationError as error:
        return malformed_result(error)
    if request.checkout is not None:
        return _remove_checkout(store, request)
    members = request.members
    named = [*members, *_pair_ends(request)]
    with store.read() as transaction:
        if not named and (not request.concept or request.program is None):
            # Nothing named: the caller's member is what is meant.
            caller = _caller_member(transaction, here)
            if isinstance(caller, SetUpResult):
                return caller
            named = [caller]
            members = () if request.concept else (caller,)
        program = _program_of(transaction, request, named)
    if isinstance(program, SetUpResult):
        return program
    return set_up(store, config, _remove_request(request, members, program), here=here)


def _remove_checkout(store: Store, request: RmRequest) -> SetUpResult:
    """``--checkout PATH`` (D8): one checkout of this machine; the member stays."""
    path = request.checkout or ""
    if request.members or request.pairs or request.concept:
        return _malformed(
            "checkout: cannot be combined with members, --pair or --concept"
        )
    if not path.startswith("/"):
        return _malformed(f"checkout: {path!r} is not an absolute path")
    with store.write() as transaction:
        machine_id = acting_machine_id(transaction)
        if delete_checkouts_at_path(transaction, machine_id, path) == 0:
            stored = [c.path for c in checkouts_on_machine(transaction, machine_id)]
            listed = ", ".join(stored) if stored else "none"
            return rejected_result(
                [
                    SetUpProblem(
                        code=SetUpProblemCode.NOT_A_CHECKOUT,
                        detail=f"no checkout of this machine is at {path!r}; this "
                        f"machine's stored paths: {listed}",
                    )
                ]
            )
    return SetUpResult(
        outcome=SetUpOutcome.APPLIED,
        change_records=(
            Change(
                verb=ChangeVerb.REMOVED, subject=ChangeSubject.CHECKOUT, detail=path
            ),
        ),
        problems=(),
        program=None,
        working_directory=None,
    )


def _malformed(detail: str) -> SetUpResult:
    return rejected_result([_problem(SetUpProblemCode.MALFORMED, detail)])


def _pair_ends(request: RmRequest) -> list[str]:
    return [end for pair in request.pairs for end in split_pair(pair)]


def _caller_member(
    transaction: Transaction, here: HereCaller | HereNotAProject | None
) -> str | SetUpResult:
    """The caller's member id, or the rejection saying why there is none."""
    if here is None:
        return _malformed(
            "nothing is named and nothing was gathered from the directory"
        )
    found = find_caller(transaction, acting_machine_id(transaction), here)
    if isinstance(found, NotAProject):
        return rejected_result(
            [
                _problem(
                    SetUpProblemCode.NOT_A_PROJECT,
                    f"{NOT_A_PROJECT_DETAIL} (cf said: {found.message})",
                )
            ]
        )
    if isinstance(found, NotInProgram):
        return rejected_result(
            [
                _problem(
                    SetUpProblemCode.NOT_A_MEMBER,
                    "this Context Forge project is in no program and no member was "
                    "named",
                )
            ]
        )
    return found.project_id


def _program_of(
    transaction: Transaction, request: RmRequest, named: list[str]
) -> str | SetUpResult:
    """The one program the request is about, or the rejection saying why not."""
    problems: list[SetUpProblem] = []
    programs: dict[str, set[str]] = {}
    for reference in named:
        stored = find_member_for_removal(transaction, reference)
        if stored is None:
            problems.append(_not_a_member(reference))
        else:
            programs.setdefault(stored.program_id, set()).add(reference)
    named_exists = (
        request.program is not None
        and get_program(transaction, request.program) is not None
    )
    if problems:
        return rejected_result(problems)
    chosen = request.program
    if chosen is None:
        chosen = next(iter(programs))
    elif not programs and not named_exists:
        return rejected_result(
            [
                _problem(
                    SetUpProblemCode.MALFORMED, f"program: {chosen!r} does not exist"
                )
            ]
        )
    others = {name: texts for name, texts in programs.items() if name != chosen}
    if others:
        listed = "; ".join(
            f"{', '.join(sorted(texts))} in {name!r}" for name, texts in others.items()
        )
        return rejected_result(
            [
                _problem(
                    SetUpProblemCode.MEMBER_OF_OTHER_PROGRAM,
                    f"rm works on one program ({chosen!r}); not in it: {listed}",
                )
            ]
        )
    return chosen


def _problem(code: SetUpProblemCode, detail: str) -> SetUpProblem:
    return SetUpProblem(code=code, detail=detail)


def _not_a_member(reference: str) -> SetUpProblem:
    return _problem(
        SetUpProblemCode.NOT_A_MEMBER,
        f"{reference!r} is not and was never a member of any program",
    )


def _remove_request(
    request: RmRequest, members: tuple[str, ...], program: str
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "program": program,
        "remove": {
            "members": list(members),
            "pairs": [
                {"provider": provider, "consumer": consumer}
                for provider, consumer in map(split_pair, request.pairs)
            ],
        },
    }
    if request.concept:
        document["concept"] = None  # given and null: clears the concept
    return document
