"""Payload models for the two program submission kinds.

Unlike the project envelope's payloads, **unknown keys are refused**: a
misspelled key here would silently drop a setting. Every validation error names
the field it is about. Field names are the constants in
``amoeba.store.program_models``; a test pins the two together.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from typing import Annotated, Final, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from amoeba.store.paths import (
    validate_path_component,
    validate_project_id,
    validate_repo_relative_path,
)
from amoeba.store.program_models import (
    REQUESTS_INITIATIVE_MAX,
    REQUESTS_INITIATIVE_MIN,
    ConsumptionMode,
    ProgramSubmissionKind,
)

#: Unknown keys fail, and validated models are immutable.
PROGRAM_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True)


def _project_id(value: str) -> str:
    validate_project_id(value)
    return value


def _program_id(value: str) -> str:
    validate_path_component(value, name="program_id")
    return value


ProjectId = Annotated[StrictStr, AfterValidator(_project_id)]
ProgramId = Annotated[StrictStr, AfterValidator(_program_id)]

#: A concept path: stripped, non-blank, and a repo-relative file with no wildcard.
ConceptPath = Annotated[
    StrictStr,
    StringConstraints(strip_whitespace=True, min_length=1),
    AfterValidator(partial(validate_repo_relative_path, glob_allowed=False)),
]


class MemberPayload(BaseModel):
    """One member of a program, and how every other member consumes it."""

    model_config = PROGRAM_MODEL_CONFIG

    project_id: ProjectId
    requests_initiative: Annotated[
        StrictInt, Field(ge=REQUESTS_INITIATIVE_MIN, le=REQUESTS_INITIATIVE_MAX)
    ]
    consumed: ConsumptionMode
    #: Required, and ``{}`` when there are none, so an omitted key never silently
    #: means "no exceptions".
    overrides: dict[ProjectId, ConsumptionMode]

    @model_validator(mode="after")
    def _overrides_do_not_name_the_member(self) -> Self:
        if self.project_id in self.overrides:
            raise ValueError(
                f"overrides must not name the member itself: {self.project_id!r}"
            )
        return self


class RegisterProgramPayload(BaseModel):
    """Creates a program, or replaces an existing one whole."""

    model_config = PROGRAM_MODEL_CONFIG

    program_id: ProgramId
    concept_member: ProjectId
    concept_path: ConceptPath
    members: Annotated[list[MemberPayload], Field(min_length=1)]

    @field_validator("members")
    @classmethod
    def _no_project_twice(cls, members: list[MemberPayload]) -> list[MemberPayload]:
        ids = [member.project_id for member in members]
        repeated = sorted({pid for pid in ids if ids.count(pid) > 1})
        if repeated:
            raise ValueError(f"project ids listed twice: {repeated}")
        return members


class RegisterMemberPayload(BaseModel):
    """Upserts one member into an existing program."""

    model_config = PROGRAM_MODEL_CONFIG

    program_id: ProgramId
    member: MemberPayload


#: The kind-to-payload-model table, defined once. A kind missing here fails a
#: test, not a user.
PROGRAM_KIND_PAYLOAD_MODELS: Final[Mapping[ProgramSubmissionKind, type[BaseModel]]] = {
    ProgramSubmissionKind.REGISTER_PROGRAM: RegisterProgramPayload,
    ProgramSubmissionKind.REGISTER_MEMBER: RegisterMemberPayload,
}
