"""The ``set_up`` request and result (slice 222, D7).

Frozen pydantic models. 226 uses ``SetUpRequest`` as the MCP tool's input schema and
``SetUpResult`` as its output. ``concept`` distinguishes omitted (leave it) from null
(no concept) by ``model_fields_set``; the list fields distinguish omitted (leave the
stored value) from given (replace it) the same way.
"""

from __future__ import annotations

from enum import StrEnum
from functools import partial
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    StrictStr,
    StringConstraints,
    model_validator,
)

from amoeba.answering.settings import RulesPath, validate_repo_relative_path
from amoeba.store.vocabulary import ConsumedMode

NonBlankText = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1)
]
#: A concept path: repo-relative and contained, with no wildcard at all.
ConceptPath = Annotated[
    NonBlankText,
    AfterValidator(partial(validate_repo_relative_path, glob_allowed=False)),
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- request -----------------------------------------------------------------


class ConceptRequest(_Model):
    #: A Context Forge project name or id.
    member: NonBlankText
    path: ConceptPath


class DependsOnRequest(_Model):
    #: A Context Forge project name or id.
    provider: NonBlankText
    consumed: ConsumedMode


class MemberRequest(_Model):
    #: A Context Forge project name or id; omitted means the working directory's.
    project: NonBlankText | None = None
    rules_paths: tuple[RulesPath, ...] | None = None
    authorize_allow: tuple[NonBlankText, ...] | None = None
    authorize_deny: tuple[NonBlankText, ...] | None = None
    depends_on: tuple[DependsOnRequest, ...] = ()

    @model_validator(mode="after")
    def _no_key_in_both_lists(self) -> Self:
        both = set(self.authorize_allow or ()) & set(self.authorize_deny or ())
        if both:
            raise ValueError(
                f"{sorted(both)} in both authorize_allow and authorize_deny"
            )
        return self


class RemovePairRequest(_Model):
    #: Context Forge project names or ids.
    provider: NonBlankText
    consumer: NonBlankText


class RemoveRequest(_Model):
    """What ``set_up`` takes out (228 D8). Members are removed softly, pairs deleted."""

    #: Context Forge project names or ids.
    members: tuple[NonBlankText, ...] = ()
    pairs: tuple[RemovePairRequest, ...] = ()


class SetUpRequest(_Model):
    program: NonBlankText
    #: Omitted leaves the concept alone; null clears it.
    concept: ConceptRequest | None = None
    members: tuple[MemberRequest, ...] = ()
    #: Omitted removes nothing.
    remove: RemoveRequest = RemoveRequest()


# --- result ------------------------------------------------------------------


class SetUpOutcome(StrEnum):
    APPLIED = "applied"
    UNCHANGED = "unchanged"
    REJECTED = "rejected"


class SetUpProblemCode(StrEnum):
    """Why a request was rejected; one per problem (D7)."""

    MALFORMED = "malformed"
    NOT_A_PROJECT = "not_a_project"
    EMPTY_PROGRAM = "empty_program"
    MEMBER_OF_OTHER_PROGRAM = "member_of_other_program"
    RULES_PATHS_REQUIRED = "rules_paths_required"
    UNKNOWN_PROVIDER = "unknown_provider"
    SELF_DEPENDENCY = "self_dependency"
    UNKNOWN_AUTHORIZE_ITEM = "unknown_authorize_item"
    CONCEPT_MEMBER_NOT_MEMBER = "concept_member_not_member"
    MEMBER_HAS_OPEN_QUESTIONS = "member_has_open_questions"
    NOT_A_MEMBER = "not_a_member"


class SetUpProblem(_Model):
    code: SetUpProblemCode
    #: Names the field or member at fault.
    detail: str


class ConceptState(_Model):
    member: str
    path: str


class DependencyState(_Model):
    provider: str
    consumed: ConsumedMode


class MemberState(_Model):
    """A member as stored; ids are Context Forge project ids."""

    project_id: str
    rules_paths: tuple[str, ...]
    authorize_allow: tuple[str, ...]
    authorize_deny: tuple[str, ...]
    #: The pairs with this member as consumer.
    depends_on: tuple[DependencyState, ...]


class ProgramState(_Model):
    program_id: str
    concept: ConceptState | None
    members: tuple[MemberState, ...]


class WorkingDirectoryMember(_Model):
    member: MemberState
    program: str


class WorkingDirectoryNotInProgram(_Model):
    #: The Context Forge id of the project the directory belongs to.
    not_in_program: str


class WorkingDirectoryNotAProject(_Model):
    #: Context Forge's message.
    not_a_project: str


type WorkingDirectory = (
    WorkingDirectoryMember | WorkingDirectoryNotInProgram | WorkingDirectoryNotAProject
)


class SetUpResult(_Model):
    outcome: SetUpOutcome
    #: One line per created or changed row; empty unless applied.
    changes: tuple[str, ...]
    #: Empty unless rejected.
    problems: tuple[SetUpProblem, ...]
    #: The program as stored after the call; null when it does not exist.
    program: ProgramState | None
    #: Informational. Null when the request was malformed and nothing was looked up.
    working_directory: WorkingDirectory | None
