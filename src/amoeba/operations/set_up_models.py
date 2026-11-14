"""The ``set_up`` request and result (slice 222, D7).

Frozen pydantic models. 226 uses ``SetUpRequest`` as the MCP tool's input schema and
``SetUpResult`` as its output. ``concept`` distinguishes omitted (leave it) from null
(no concept) by ``model_fields_set``; the list fields distinguish omitted (leave the
stored value) from given (replace it) the same way.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from functools import partial
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    StrictStr,
    StringConstraints,
    computed_field,
    model_validator,
)

from amoeba.answering.settings import RulesPath, validate_repo_relative_path
from amoeba.store.vocabulary import ConsumedMode, RulesFrom

NonBlankText = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1)
]
#: A concept path: repo-relative and contained, with no wildcard at all.
ConceptPath = Annotated[
    NonBlankText,
    AfterValidator(partial(validate_repo_relative_path, glob_allowed=False)),
]


class FrozenModel(BaseModel):
    """The base of the request and result models: no extra keys, frozen."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# --- request -----------------------------------------------------------------


class ConceptRequest(FrozenModel):
    #: A Context Forge project name or id.
    member: NonBlankText
    path: ConceptPath


class DependsOnRequest(FrozenModel):
    #: A Context Forge project name or id.
    provider: NonBlankText
    consumed: ConsumedMode


class MemberRequest(FrozenModel):
    #: A Context Forge project name or id; omitted means the working directory's.
    project: NonBlankText | None = None
    #: Omitted leaves the member's rules (a new member gets the config default);
    #: given, including ``[]`` (no rules), replaces them and makes them named.
    rules_paths: tuple[RulesPath, ...] | None = None
    #: True returns the member to the config's default rules (229 D7).
    rules_default: bool = False
    authorize_allow: tuple[NonBlankText, ...] | None = None
    authorize_deny: tuple[NonBlankText, ...] | None = None
    depends_on: tuple[DependsOnRequest, ...] = ()

    @model_validator(mode="after")
    def _rules_named_or_default(self) -> Self:
        if self.rules_default and self.rules_paths is not None:
            raise ValueError("rules_default and rules_paths cannot both be given")
        return self

    @model_validator(mode="after")
    def _no_key_in_both_lists(self) -> Self:
        both = set(self.authorize_allow or ()) & set(self.authorize_deny or ())
        if both:
            raise ValueError(
                f"{sorted(both)} in both authorize_allow and authorize_deny"
            )
        return self


class RemovePairRequest(FrozenModel):
    #: Context Forge project names or ids.
    provider: NonBlankText
    consumer: NonBlankText


class RemoveRequest(FrozenModel):
    """What ``set_up`` takes out (228 D8). Members are removed softly, pairs deleted."""

    #: Context Forge project names or ids.
    members: tuple[NonBlankText, ...] = ()
    pairs: tuple[RemovePairRequest, ...] = ()


class SetUpRequest(FrozenModel):
    program: NonBlankText
    #: Omitted leaves the concept alone; null clears it.
    concept: ConceptRequest | None = None
    members: tuple[MemberRequest, ...] = ()
    #: Omitted removes nothing.
    remove: RemoveRequest = RemoveRequest()


# --- result ------------------------------------------------------------------


class ChangeVerb(StrEnum):
    """The first word of a change line."""

    ADDED = "added"
    UPDATED = "updated"
    REMOVED = "removed"


class ChangeSubject(StrEnum):
    """The second word of a change line: the kind of row it names."""

    PROGRAM = "program"
    MEMBER = "member"
    DEPENDENCY = "dependency"
    PAIR = "pair"


class Change(FrozenModel):
    """One created, changed or removed row: what the engine did, as data."""

    verb: ChangeVerb
    subject: ChangeSubject
    #: What the row is, with Context Forge ids (``consumer on provider (mode)`` for a
    #: dependency, ``provider -> consumer`` for a pair).
    detail: str

    @property
    def line(self) -> str:
        """The change as one line of text: ``<verb> <subject> <detail>``."""
        return f"{self.verb.value} {self.subject.value} {self.detail}"


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
    UNKNOWN_PROVIDER = "unknown_provider"
    SELF_DEPENDENCY = "self_dependency"
    UNKNOWN_AUTHORIZE_ITEM = "unknown_authorize_item"
    CONCEPT_MEMBER_NOT_MEMBER = "concept_member_not_member"
    MEMBER_HAS_OPEN_QUESTIONS = "member_has_open_questions"
    NOT_A_MEMBER = "not_a_member"


class OpenQuestion(FrozenModel):
    """A question key, as ``sq runs wait --json`` prints its pause."""

    run_id: str
    paused_at: str


class SetUpProblem(FrozenModel):
    code: SetUpProblemCode
    #: Names the field or member at fault.
    detail: str
    #: For ``member_has_open_questions``: the questions that block the removal, so a
    #: renderer needs no reading of ``detail``.
    open_questions: tuple[OpenQuestion, ...] = ()


class ConceptState(FrozenModel):
    member: str
    path: str


class DependencyState(FrozenModel):
    provider: str
    consumed: ConsumedMode


class MemberState(FrozenModel):
    """A member as stored; ids are Context Forge project ids."""

    project_id: str
    rules_paths: tuple[str, ...]
    #: ``config_default``: the config's ``default_rules_paths`` apply and
    #: ``rules_paths`` is unused (empty).
    rules_from: RulesFrom
    authorize_allow: tuple[str, ...]
    authorize_deny: tuple[str, ...]
    #: The pairs with this member as consumer.
    depends_on: tuple[DependencyState, ...]


class ProgramState(FrozenModel):
    program_id: str
    concept: ConceptState | None
    members: tuple[MemberState, ...]


class WorkingDirectoryMember(FrozenModel):
    member: MemberState
    program: str


class WorkingDirectoryNotInProgram(FrozenModel):
    #: The Context Forge id of the project the directory belongs to.
    not_in_program: str


class WorkingDirectoryNotAProject(FrozenModel):
    #: Context Forge's message.
    not_a_project: str


type WorkingDirectory = (
    WorkingDirectoryMember | WorkingDirectoryNotInProgram | WorkingDirectoryNotAProject
)


class SetUpResult(FrozenModel):
    outcome: SetUpOutcome
    #: What was created, changed or removed; empty unless applied.
    change_records: tuple[Change, ...]
    #: Empty unless rejected.
    problems: tuple[SetUpProblem, ...]
    #: The program as stored after the call; null when it does not exist.
    program: ProgramState | None
    #: Informational. Null when the request was malformed and nothing was looked up.
    working_directory: WorkingDirectory | None

    @computed_field
    @property
    def changes(self) -> tuple[str, ...]:
        """One line of text per change record: what ``-j`` shows to a person."""
        return tuple(record.line for record in self.change_records)


def rejected_result(
    problems: Sequence[SetUpProblem],
    working_directory: WorkingDirectory | None = None,
) -> SetUpResult:
    """A rejection made before the engine ran: nothing written, no program shown."""
    return SetUpResult(
        outcome=SetUpOutcome.REJECTED,
        change_records=(),
        problems=tuple(problems),
        program=None,
        working_directory=working_directory,
    )
