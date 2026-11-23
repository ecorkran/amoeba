"""``list``: what needs the PM, and what is registered (slice 229, D3).

With no subject it is the ``status`` operation, same code and same sweep: the
:class:`ListResult` holds ``status``'s result unchanged. ``all`` adds the questions
that settled within ``prune_after_days`` (``settled``); the run lists the person's
view also needs are already in the status document. The subjects ``programs``,
``members`` and ``dependencies`` give the registered views of ``list_registry``, and
``standing`` the standing answers (slice 230, D4), with ``all`` adding withdrawn ones.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Final

from pydantic import ValidationError, field_validator

from amoeba.answering.values import AnsweredBy
from amoeba.config.user_config import NonBlank, UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.here_document import HereCaller, HereNotAProject
from amoeba.operations.list_registry import (
    DependenciesView,
    MembersView,
    ProgramsView,
    StandingView,
    dependencies_view,
    members_view,
    programs_view,
    standing_view,
)
from amoeba.operations.reject_codes import (
    RejectCode,
    unknown_program_problem,
    validation_problems,
)
from amoeba.operations.runs_document import RunsDocument
from amoeba.operations.set_up_models import FrozenModel
from amoeba.operations.status import status
from amoeba.operations.status_models import StatusOutcome, StatusResult
from amoeba.store.errors import StoreRowError
from amoeba.store.programs import get_member_any
from amoeba.store.settled import SettledQuestion, settled_since
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import ClosedReason


class ListSubject(StrEnum):
    """What ``list`` shows besides the default view."""

    PROGRAMS = "programs"
    MEMBERS = "members"
    DEPENDENCIES = "dependencies"
    STANDING = "standing"


#: The singular forms the CLI and the tool also take; each names one subject.
SUBJECT_ALIASES: Final[Mapping[str, ListSubject]] = {
    "program": ListSubject.PROGRAMS,
    "member": ListSubject.MEMBERS,
    "dependency": ListSubject.DEPENDENCIES,
}
#: The subjects ``all`` does not apply to.
ALL_NOT_ACCEPTED: Final = frozenset({ListSubject.MEMBERS, ListSubject.DEPENDENCIES})
#: The subjects ``program`` does not apply to: a standing answer of reach ``all``
#: reaches every program, so no program narrows the list honestly.
PROGRAM_NOT_ACCEPTED: Final = frozenset({ListSubject.STANDING})


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


type ListOutcome = (
    ListResult | ProgramsView | MembersView | DependenciesView | StandingView
)


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
    here: HereCaller | HereNotAProject | None,
    runs: RunsDocument | None,
    deps: Deps,
) -> ListOutcome:
    """Apply the ``list`` request ``document``, which is validated here.

    ``here`` is the caller's gathered project and ``runs`` the machine's gathered runs,
    both needed by the default view only (``needs_here`` says when).

    Raises:
        SquadronError: The runs document says ``sq runs list --json`` gave no usable
            listing (default view).
        StoreError: The store cannot be used.
    """
    try:
        request = ListRequest.model_validate(document)
    except ValidationError as error:
        return _rejected(RejectCode.MALFORMED, validation_problems(error))
    if request.subject is None:
        return _default_view(store, config, request, here, runs, deps)
    if request.all and request.subject in ALL_NOT_ACCEPTED:
        return _rejected(
            RejectCode.MALFORMED,
            (f"all does not apply to {request.subject.value}",),
        )
    if request.program is not None and request.subject in PROGRAM_NOT_ACCEPTED:
        return _rejected(
            RejectCode.MALFORMED,
            (f"program does not apply to {request.subject.value}",),
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
            return members_view(store, config, program=request.program)
        case ListSubject.DEPENDENCIES:
            return dependencies_view(store, program=request.program)
        case ListSubject.STANDING:
            return standing_view(store, include_withdrawn=request.all)


def _default_view(
    store: Store,
    config: UserConfig,
    request: ListRequest,
    here: HereCaller | HereNotAProject | None,
    runs: RunsDocument | None,
    deps: Deps,
) -> ListResult:
    if here is None or runs is None:
        raise ValueError("the default list view needs the gathered caller and runs")
    result = status(
        store,
        config,
        {} if request.program is None else {"program": request.program},
        here=here,
        runs=runs,
        deps=deps,
    )
    if not request.all or result.outcome is StatusOutcome.REJECTED:
        return ListResult(status=result)
    since = deps.clock() - timedelta(days=config.prune_after_days)
    with store.read() as transaction:
        settled = settled_since(transaction, since)
        names = {
            item.member_id: _stored_name(transaction, item.member_id)
            for item in settled
        }
    return ListResult(
        status=result,
        settled=tuple(
            _entry(item, names) for item in settled if _in_scope(item, request.program)
        ),
    )


def _stored_name(transaction: Transaction, member_id: str) -> str:
    """The name the store holds for a member, removed members included."""
    member = get_member_any(transaction, member_id)
    if member is None:
        raise StoreRowError(f"settled question of {member_id!r}, a member not in store")
    return member.name


def needs_here(document: object) -> bool:
    """Whether the gathered caller and runs are needed: the default view (no subject)
    only.

    A document that does not parse needs nothing; ``list_view`` rejects it."""
    try:
        request = ListRequest.model_validate(document)
    except ValidationError:
        # Not a valid request: list_view returns the malformed rejection, no caller.
        return False
    return request.subject is None


def _in_scope(item: SettledQuestion, program: str | None) -> bool:
    return program is None or item.program_id == program


def _entry(item: SettledQuestion, names: Mapping[str, str]) -> SettledEntry:
    return SettledEntry(
        program=item.program_id,
        member_id=item.member_id,
        member_name=names[item.member_id],
        run_id=item.key.run_id,
        paused_at=item.key.paused_at,
        question=item.question,
        ended=item.ended,
        settled_at=item.settled_at,
    )
