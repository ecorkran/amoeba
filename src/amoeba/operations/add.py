"""``add``: register the working directory's repo, or any repo (slice 229, D4, D5).

``add`` builds a ``SetUpRequest`` and calls the ``set_up`` engine, so every guard and
every result field is the engine's. The request is either ``bulk`` (a whole
``SetUpRequest``, handed over as given) or the fields of one member; never both.

Program choice (D5): the request's ``program``; else the program the member already
belongs to (a removed member's too, so ``rm`` then ``add`` revives it where it was);
else a new program named for the member's Context Forge project.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Self

from pydantic import ValidationError, model_validator

from amoeba.answering.settings import RulesPath
from amoeba.config.user_config import UserConfig
from amoeba.operations.project_lookup import project_or_rejection
from amoeba.operations.set_up import malformed_result, set_up
from amoeba.operations.set_up_models import (
    ConceptRequest,
    DependsOnRequest,
    FrozenModel,
    MemberRequest,
    NonBlankText,
    SetUpRequest,
    SetUpResult,
)
from amoeba.store.programs import get_member_any
from amoeba.store.store import Store
from amoeba.store.vocabulary import ConsumedMode
from amoeba.upstream.context_forge.cli_call import CfRun
from amoeba.upstream.context_forge.project_of import (
    CFProject,
    project_of,
)

#: No door-specific wording: each door (the CLI renderer, MCP) adds its own fix.
NOT_A_PROJECT_DETAIL: Final = "this directory is not a Context Forge project"


class AddDependsOn(FrozenModel):
    #: A Context Forge project name or id.
    provider: NonBlankText
    #: Omitted takes the config's ``default_consumed``.
    consumed: ConsumedMode | None = None


class AddRequest(FrozenModel):
    """``bulk``, or the fields of one member. Omitted differs from given."""

    bulk: SetUpRequest | None = None
    program: NonBlankText | None = None
    #: A Context Forge project name or id; omitted means the working directory's.
    project: NonBlankText | None = None
    rules_paths: tuple[RulesPath, ...] | None = None
    rules_default: bool = False
    authorize_allow: tuple[NonBlankText, ...] | None = None
    authorize_deny: tuple[NonBlankText, ...] | None = None
    depends_on: tuple[AddDependsOn, ...] = ()
    concept: ConceptRequest | None = None

    @model_validator(mode="after")
    def _bulk_or_single(self) -> Self:
        singles = sorted(self.model_fields_set - {"bulk"})
        if "bulk" in self.model_fields_set and self.bulk is None:
            # An empty request file parses to null: not a request, never "no flags".
            raise ValueError("bulk must be a request document, not null")
        if self.bulk is not None and singles:
            raise ValueError(f"bulk cannot be combined with {', '.join(singles)}")
        return self


def single_member_request(
    request: AddRequest, config: UserConfig, program_id: str
) -> SetUpRequest:
    """The ``SetUpRequest`` for the one member; omitted fields stay omitted."""
    given = request.model_fields_set
    member: dict[str, Any] = {
        name: getattr(request, name)
        for name in (
            "rules_paths",
            "rules_default",
            "authorize_allow",
            "authorize_deny",
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
    document: dict[str, Any] = {
        "program": program_id,
        "members": (
            MemberRequest.model_validate({"project": request.project, **member}),
        ),
    }
    if "concept" in given:
        document["concept"] = request.concept
    return SetUpRequest.model_validate(document)


def add(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    directory: Path,
    run: CfRun,
) -> SetUpResult:
    """Apply the ``add`` request ``document``, which is validated here.

    Raises:
        ContextForgeError: ``cf`` failed to give a usable answer; nothing is written.
        StoreError: The store failed.
    """
    try:
        request = AddRequest.model_validate(document)
    except ValidationError as error:
        return malformed_result(error)
    if request.bulk is not None:
        return set_up(store, config, request.bulk, directory=directory, run=run)
    project = _member_project(request, directory, run)
    if isinstance(project, SetUpResult):
        return project
    program_id = _program_for(store, request, project)
    try:
        built = single_member_request(request, config, program_id)
    except ValidationError as error:
        # The member's own rules (rules_default with rules_paths, a key both allowed
        # and denied) are checked here, so they are `malformed` like any bad request.
        return malformed_result(error)
    return set_up(store, config, built, directory=directory, run=run)


def _member_project(
    request: AddRequest, directory: Path, run: CfRun
) -> CFProject | SetUpResult:
    """The member's Context Forge project, or the rejection that ends the call."""
    if request.project is None:
        return project_or_rejection(
            project_of(directory=directory, run=run), NOT_A_PROJECT_DETAIL
        )
    return project_or_rejection(
        project_of(reference=request.project, run=run),
        f"project {request.project!r}",
    )


def _program_for(store: Store, request: AddRequest, project: CFProject) -> str:
    if request.program is not None:
        return request.program
    with store.read() as transaction:
        stored = get_member_any(transaction, project.id)
    return project.name if stored is None else stored.program_id
