"""``rm``: remove members, pairs or the concept from a program (slice 229, D6).

``rm`` finds the program from the store, builds the ``remove`` section of a
``SetUpRequest`` and calls the ``set_up`` engine, so soft removal, open-question
refusals and ``not_a_member`` are the engine's. With nothing named, it removes the
working directory's project. A member is named by Context Forge name or id; one
Context Forge no longer knows is read as a stored id, so a deleted project can still
be removed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from pydantic import ValidationError, field_validator

from amoeba.config.user_config import UserConfig
from amoeba.operations.members import ContextForgeError
from amoeba.operations.project_lookup import project_or_rejection
from amoeba.operations.set_up import malformed_result, set_up
from amoeba.operations.set_up_models import (
    FrozenModel,
    NonBlankText,
    SetUpProblem,
    SetUpProblemCode,
    SetUpResult,
    rejected_result,
)
from amoeba.store.programs import get_member_any, get_program
from amoeba.store.store import Store
from amoeba.upstream.context_forge.cli_call import CfCallFailed, CfRun
from amoeba.upstream.context_forge.project_of import CFProject, project_of

PAIR_SEPARATOR: Final = ":"
#: No door-specific wording: each door (the CLI renderer, MCP) adds its own fix.
NOT_A_PROJECT_DETAIL: Final = (
    "this directory is not a Context Forge project and no member was named"
)


class RmRequest(FrozenModel):
    #: Context Forge project names or ids. None named (and no pair, no concept)
    #: means the working directory's project.
    members: tuple[NonBlankText, ...] = ()
    #: ``PROVIDER:CONSUMER``, each a Context Forge project name or id.
    pairs: tuple[NonBlankText, ...] = ()
    #: Clear the program's concept, the only way to remove the concept's member.
    concept: bool = False
    #: The program, when it cannot be told from the members.
    program: NonBlankText | None = None

    @field_validator("pairs")
    @classmethod
    def _each_pair_has_two_ends(cls, pairs: tuple[str, ...]) -> tuple[str, ...]:
        for pair in pairs:
            provider, separator, consumer = pair.partition(PAIR_SEPARATOR)
            if not (separator and provider.strip() and consumer.strip()):
                raise ValueError(f"{pair!r} must be PROVIDER{PAIR_SEPARATOR}CONSUMER")
        return pairs


@dataclass(frozen=True)
class _Anchor:
    """A named member (or pair end): as written, and its stored id."""

    text: str
    project_id: str


def split_pair(pair: str) -> tuple[str, str]:
    provider, _, consumer = pair.partition(PAIR_SEPARATOR)
    return provider.strip(), consumer.strip()


def rm(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    directory: Path,
    run: CfRun,
) -> SetUpResult:
    """Apply the ``rm`` request ``document``, which is validated here.

    Raises:
        ContextForgeError: ``cf`` failed to give a usable answer; nothing is written.
        StoreError: The store failed.
    """
    try:
        request = RmRequest.model_validate(document)
    except ValidationError as error:
        return malformed_result(error)
    members = request.members
    anchors = [_anchor(text, run) for text in (*members, *_pair_ends(request))]
    if not anchors and (not request.concept or request.program is None):
        # Nothing named: the working directory's project is what is meant.
        found = _working_directory_project(directory, run)
        if isinstance(found, SetUpResult):
            return found
        anchors = [_Anchor(found.name, found.id)]
        members = () if request.concept else (found.id,)
    program = _program_of(store, request, anchors)
    if isinstance(program, SetUpResult):
        return program
    return set_up(
        store,
        config,
        _remove_request(request, members, program),
        directory=directory,
        run=run,
    )


def _pair_ends(request: RmRequest) -> list[str]:
    return [end for pair in request.pairs for end in split_pair(pair)]


def _working_directory_project(directory: Path, run: CfRun) -> CFProject | SetUpResult:
    return project_or_rejection(
        project_of(directory=directory, run=run), NOT_A_PROJECT_DETAIL
    )


def _anchor(text: str, run: CfRun) -> _Anchor:
    """A reference as its Context Forge id; one cf does not know is read as an id."""
    found = project_of(reference=text, run=run)
    if isinstance(found, CfCallFailed):
        raise ContextForgeError(found.detail)
    return _Anchor(text, found.id if isinstance(found, CFProject) else text)


def _program_of(
    store: Store, request: RmRequest, anchors: list[_Anchor]
) -> str | SetUpResult:
    """The one program the request is about, or the rejection saying why not."""
    problems: list[SetUpProblem] = []
    programs: dict[str, set[str]] = {}
    with store.read() as transaction:
        for anchor in anchors:
            stored = get_member_any(transaction, anchor.project_id)
            if stored is None:
                problems.append(_not_a_member(anchor))
            else:
                programs.setdefault(stored.program_id, set()).add(anchor.text)
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


def _not_a_member(anchor: _Anchor) -> SetUpProblem:
    return _problem(
        SetUpProblemCode.NOT_A_MEMBER,
        f"{anchor.text!r} ({anchor.project_id}) is not and was never a member of "
        "any program",
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
