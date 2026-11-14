"""``list``: what needs the PM, and what is registered (slice 229, D3).

With no subject it is the ``status`` operation, same code and same sweep: the
:class:`ListResult` holds ``status``'s result unchanged. ``all`` adds the questions
that settled within ``prune_after_days`` (``settled``); the run lists the person's
view also needs are already in the status document. The subjects ``programs``,
``members`` and ``dependencies`` give the registered views of ``list_registry``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from pydantic import ValidationError, field_validator

from amoeba.answering.values import AnsweredBy
from amoeba.config.user_config import NonBlank, UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.list_registry import (
    DependenciesView,
    MembersView,
    ProgramsView,
    dependencies_view,
    members_view,
    programs_view,
)
from amoeba.operations.members import ContextForgeError
from amoeba.operations.reject_codes import (
    RejectCode,
    unknown_program_problem,
    validation_problems,
)
from amoeba.operations.set_up_models import FrozenModel
from amoeba.operations.status import status
from amoeba.operations.status_models import StatusOutcome, StatusResult
from amoeba.store.settled import SettledQuestion, settled_since
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason
from amoeba.upstream.context_forge.cli_call import CfCallFailed


class ListSubject(StrEnum):
    """What ``list`` shows besides the default view."""

    PROGRAMS = "programs"
    MEMBERS = "members"
    DEPENDENCIES = "dependencies"


#: The singular forms the CLI and the tool also take; each names one subject.
SUBJECT_ALIASES: Final[Mapping[str, ListSubject]] = {
    "program": ListSubject.PROGRAMS,
    "member": ListSubject.MEMBERS,
    "dependency": ListSubject.DEPENDENCIES,
}
#: The subjects ``all`` does not apply to.
ALL_NOT_ACCEPTED: Final = frozenset({ListSubject.MEMBERS, ListSubject.DEPENDENCIES})


class ListRequest(FrozenModel):
    subject: ListSubject | None = None
    #: Default view: add what settled. ``programs``: add programs with no members.
    all: bool = False
    program: NonBlank | None = None

    @field_validator("subject", mode="before")
    @classmethod
    def _singular_names_the_same_subject(cls, value: Any) -> Any:
        if isinstance(value, str) and value in SUBJECT_ALIASES:
            return SUBJECT_ALIASES[value]
        return value


class SettledEntry(FrozenModel):
    """A question that settled recently, for the PM's own review."""

    program: str
    member_id: str
    #: Null when Context Forge no longer lists the member.
    member_name: str | None
    run_id: str
    paused_at: str
    question: str
    #: ``pm`` or ``answerer`` for an answer; a closed reason otherwise.
    ended: AnsweredBy | ClosedReason
    settled_at: datetime


class ListResult(FrozenModel):
    """The default view: ``status``'s result, and ``settled`` when ``all`` was given."""

    status: StatusResult
    #: ``None`` when ``all`` was not given.
    settled: tuple[SettledEntry, ...] | None = None

    def document(self) -> dict[str, object]:
        """``status``'s document; with ``all``, plus one top-level ``settled``."""
        document = self.status.model_dump(mode="json")
        if self.settled is not None:
            document["settled"] = [e.model_dump(mode="json") for e in self.settled]
        return document


type ListOutcome = ListResult | ProgramsView | MembersView | DependenciesView


def _rejected(code: RejectCode, problems: tuple[str, ...]) -> ListResult:
    return ListResult(
        status=StatusResult(
            outcome=StatusOutcome.REJECTED, rejection=code, problems=problems
        )
    )


def list_view(
    store: Store,
    config: UserConfig,
    document: object,
    *,
    directory: Path,
    deps: Deps,
) -> ListOutcome:
    """Apply the ``list`` request ``document``, which is validated here.

    Raises:
        SquadronError: ``sq runs list --json`` gave no usable listing (default view).
        ContextForgeError: ``cf`` gave no usable answer.
        StoreError: The store cannot be used.
    """
    try:
        request = ListRequest.model_validate(document)
    except ValidationError as error:
        return _rejected(RejectCode.MALFORMED, validation_problems(error))
    if request.subject is None:
        return _default_view(store, config, request, directory, deps)
    if request.all and request.subject in ALL_NOT_ACCEPTED:
        return _rejected(
            RejectCode.MALFORMED,
            (f"all does not apply to {request.subject.value}",),
        )
    if request.program is not None:
        with store.read() as transaction:
            unknown = unknown_program_problem(transaction, request.program)
        if unknown is not None:
            return _rejected(RejectCode.UNKNOWN_PROGRAM, (unknown,))
    match request.subject:
        case ListSubject.PROGRAMS:
            return programs_view(store, program=request.program, show_empty=request.all)
        case ListSubject.MEMBERS:
            return members_view(store, config, deps.cf_run, program=request.program)
        case ListSubject.DEPENDENCIES:
            return dependencies_view(store, deps.cf_run, program=request.program)


def _default_view(
    store: Store,
    config: UserConfig,
    request: ListRequest,
    directory: Path,
    deps: Deps,
) -> ListResult:
    result = status(
        store,
        config,
        {} if request.program is None else {"program": request.program},
        directory=directory,
        deps=deps,
    )
    if not request.all or result.outcome is StatusOutcome.REJECTED:
        return ListResult(status=result)
    since = deps.clock() - timedelta(days=config.prune_after_days)
    with store.read() as transaction:
        settled = settled_since(transaction, since)
    names = deps.project_names()
    if isinstance(names, CfCallFailed):
        raise ContextForgeError(names.detail)
    return ListResult(
        status=result,
        settled=tuple(
            _entry(item, names) for item in settled if _in_scope(item, request.program)
        ),
    )


def _in_scope(item: SettledQuestion, program: str | None) -> bool:
    return program is None or item.program_id == program


def _entry(item: SettledQuestion, names: Mapping[str, str]) -> SettledEntry:
    return SettledEntry(
        program=item.program_id,
        member_id=item.member_id,
        member_name=names.get(item.member_id),
        run_id=item.key.run_id,
        paused_at=item.key.paused_at,
        question=item.question,
        ended=item.ended,
        settled_at=item.settled_at,
    )
